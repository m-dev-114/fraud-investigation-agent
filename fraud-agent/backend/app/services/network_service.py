from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models as m


def build_network(db: Session, transaction_id: str, hops: int = 1):
    """
    Builds a Customer -> Device -> IP -> Merchant -> Transaction graph centered
    on the given transaction, expanding to other transactions that share the
    same device or IP (the signal used to surface fraud rings).
    """
    txn = db.query(m.Transaction).filter(m.Transaction.id == transaction_id).first()
    if txn is None:
        raise ValueError(f"Transaction {transaction_id} not found")

    nodes = {}
    edges = []

    def add_node(node_id, node_type, label, risk=None, data=None):
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "type": node_type, "label": label, "risk": risk, "data": data or {}}
        return node_id

    def add_edge(source, target, label=None):
        eid = f"e_{source}_{target}"
        edges.append({"id": eid, "source": source, "target": target, "label": label})

    customer = db.query(m.Customer).filter(m.Customer.id == txn.customer_id).first()
    merchant = db.query(m.Merchant).filter(m.Merchant.id == txn.merchant_id).first()

    cust_node = add_node(customer.id, "customer", customer.full_name,
                          risk=customer.risk_segment, data={"city": customer.city})
    txn_node = add_node(txn.id, "transaction", f"₹{txn.amount:,.0f}",
                         risk="critical" if txn.fraud_label else None,
                         data={"amount": txn.amount, "status": txn.status, "fraud_label": txn.fraud_label})
    add_edge(cust_node, txn_node, "made")

    merch_node = add_node(merchant.id, "merchant", merchant.name, risk=merchant.risk_rating,
                           data={"category": merchant.category}) if merchant else None
    if merch_node:
        add_edge(txn_node, merch_node, "paid to")

    if txn.device_id:
        device = db.query(m.Device).filter(m.Device.id == txn.device_id).first()
        if device:
            dev_node = add_node(device.id, "device", f"Device {device.device_type}",
                                 risk="high" if not device.is_trusted else None,
                                 data={"os": device.os})
            add_edge(cust_node, dev_node, "uses")
            add_edge(txn_node, dev_node, "via")

            # Other customers who used this same device (ring indicator)
            other_txns = db.query(m.Transaction).filter(
                m.Transaction.device_id == device.id, m.Transaction.customer_id != customer.id
            ).limit(15).all()
            for ot in other_txns:
                oc = db.query(m.Customer).filter(m.Customer.id == ot.customer_id).first()
                if not oc:
                    continue
                oc_node = add_node(oc.id, "customer", oc.full_name, risk=oc.risk_segment)
                ot_node = add_node(ot.id, "transaction", f"₹{ot.amount:,.0f}",
                                    risk="critical" if ot.fraud_label else None,
                                    data={"amount": ot.amount, "fraud_label": ot.fraud_label})
                add_edge(oc_node, ot_node, "made")
                add_edge(oc_node, dev_node, "uses")
                add_edge(ot_node, dev_node, "via")

    if txn.ip_address:
        ip_node = add_node(f"ip_{txn.ip_address}", "ip", txn.ip_address, data={})
        add_edge(txn_node, ip_node, "from")

        other_customers = db.query(m.IPEvent.customer_id).filter(
            m.IPEvent.ip_address == txn.ip_address, m.IPEvent.customer_id != customer.id
        ).distinct().limit(15).all()
        for (ocid,) in other_customers:
            oc = db.query(m.Customer).filter(m.Customer.id == ocid).first()
            if not oc:
                continue
            oc_node = add_node(oc.id, "customer", oc.full_name, risk=oc.risk_segment)
            add_edge(oc_node, ip_node, "from")

    return {"nodes": list(nodes.values()), "edges": edges}
