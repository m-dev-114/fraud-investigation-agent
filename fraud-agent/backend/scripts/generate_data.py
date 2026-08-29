"""
Generates reproducible synthetic fintech data for the fraud investigation demo.

Outputs CSVs under data/synthetic/:
  customers.csv, merchants.csv, devices.csv, transactions.csv,
  ip_events.csv, disputes.csv

Run:
  python scripts/generate_data.py
"""
import os
import uuid
import random
import datetime as dt
import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)

N_CUSTOMERS = 10_000
N_MERCHANTS = 1_000
N_DEVICES = 5_000
N_TRANSACTIONS = 100_000

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")
os.makedirs(OUT_DIR, exist_ok=True)

CITIES = [
    ("Mumbai", "Maharashtra", 19.0760, 72.8777),
    ("Delhi", "Delhi", 28.7041, 77.1025),
    ("Bengaluru", "Karnataka", 12.9716, 77.5946),
    ("Hyderabad", "Telangana", 17.3850, 78.4867),
    ("Chennai", "Tamil Nadu", 13.0827, 80.2707),
    ("Kolkata", "West Bengal", 22.5726, 88.3639),
    ("Pune", "Maharashtra", 18.5204, 73.8567),
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714),
    ("Jaipur", "Rajasthan", 26.9124, 75.7873),
    ("Port Blair", "Andaman and Nicobar Islands", 11.6234, 92.7265),
    ("Lucknow", "Uttar Pradesh", 26.8467, 80.9462),
    ("Kochi", "Kerala", 9.9312, 76.2673),
    ("Chandigarh", "Chandigarh", 30.7333, 76.7794),
    ("Bhopal", "Madhya Pradesh", 23.2599, 77.4126),
    ("Guwahati", "Assam", 26.1445, 91.7362),
]

# A handful of "far" foreign cities used for impossible-travel / account-takeover patterns
FOREIGN_CITIES = [
    ("Dubai", "UAE", 25.2048, 55.2708),
    ("Singapore", "Singapore", 1.3521, 103.8198),
    ("London", "UK", 51.5074, -0.1278),
    ("Lagos", "Nigeria", 6.5244, 3.3792),
    ("Moscow", "Russia", 55.7558, 37.6173),
]

MERCHANT_CATEGORIES = [
    ("Electronics", "5732"), ("Groceries", "5411"), ("Travel", "4722"),
    ("Restaurants", "5812"), ("Fashion", "5651"), ("Fuel", "5541"),
    ("Utilities", "4900"), ("Entertainment", "7832"), ("Jewelry", "5944"),
    ("Digital Goods", "5815"), ("Gambling/Gaming", "7995"), ("Crypto/Forex", "6051"),
    ("Pharmacy", "5912"), ("Education", "8220"), ("Insurance", "6300"),
]

DEVICE_TYPES = ["mobile", "desktop", "tablet"]
OS_LIST = ["iOS", "Android", "Windows", "macOS", "Linux"]
CHANNELS = ["card", "upi", "netbanking", "wallet"]

NOW = dt.datetime.utcnow()
START = NOW - dt.timedelta(days=180)


def rand_time_between(start, end):
    delta = end - start
    seconds = random.randint(0, int(delta.total_seconds()))
    return start + dt.timedelta(seconds=seconds)


def haversine_km(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
print("Generating customers...")
customers = []
risk_segments = np.random.choice(
    ["normal", "watchlist", "high_risk"], size=N_CUSTOMERS, p=[0.92, 0.06, 0.02]
)
for i in range(N_CUSTOMERS):
    cid = f"cust_{i:06d}"
    city, state, lat, lon = random.choice(CITIES)
    created = rand_time_between(NOW - dt.timedelta(days=365 * 3), NOW - dt.timedelta(days=30))
    customers.append({
        "id": cid,
        "full_name": fake.name(),
        "email": fake.unique.email(),
        "phone": fake.msisdn()[:10],
        "city": city,
        "state": state,
        "country": "IN",
        "account_created_at": created,
        "risk_segment": risk_segments[i],
        "kyc_verified": True if random.random() > 0.03 else False,
        "home_lat": lat + np.random.normal(0, 0.05),
        "home_lon": lon + np.random.normal(0, 0.05),
        "created_at": created,
    })
customers_df = pd.DataFrame(customers)

# ---------------------------------------------------------------------------
# Merchants
# ---------------------------------------------------------------------------
print("Generating merchants...")
merchants = []
for i in range(N_MERCHANTS):
    cat, mcc = random.choice(MERCHANT_CATEGORIES)
    risk = "low"
    if cat in ("Gambling/Gaming", "Crypto/Forex"):
        risk = random.choices(["medium", "high"], weights=[0.4, 0.6])[0]
    elif cat in ("Digital Goods", "Jewelry"):
        risk = random.choices(["low", "medium"], weights=[0.6, 0.4])[0]
    merchants.append({
        "id": f"merch_{i:05d}",
        "name": f"{fake.company()} {cat}",
        "category": cat,
        "mcc": mcc,
        "country": "IN",
        "risk_rating": risk,
        "avg_ticket_size": round(np.random.gamma(2.0, 800), 2),
        "created_at": rand_time_between(NOW - dt.timedelta(days=365 * 4), NOW - dt.timedelta(days=60)),
    })
merchants_df = pd.DataFrame(merchants)

# ---------------------------------------------------------------------------
# Devices (some customers have 1-2 trusted devices; some none yet)
# ---------------------------------------------------------------------------
print("Generating devices...")
devices = []
device_owner_pool = list(customers_df["id"])
random.shuffle(device_owner_pool)
di = 0
for cid in device_owner_pool:
    n_dev = np.random.choice([0, 1, 1, 2], p=[0.15, 0.55, 0.2, 0.1])
    for _ in range(n_dev):
        if di >= N_DEVICES:
            break
        first_seen = rand_time_between(NOW - dt.timedelta(days=365 * 2), NOW - dt.timedelta(days=1))
        devices.append({
            "id": f"dev_{di:06d}",
            "customer_id": cid,
            "device_fingerprint": uuid.uuid4().hex[:16],
            "device_type": random.choice(DEVICE_TYPES),
            "os": random.choice(OS_LIST),
            "first_seen_at": first_seen,
            "last_seen_at": rand_time_between(first_seen, NOW),
            "is_trusted": True,
        })
        di += 1
    if di >= N_DEVICES:
        break
devices_df = pd.DataFrame(devices)
customer_devices = devices_df.groupby("customer_id")["id"].apply(list).to_dict()

print(f"  customers={len(customers_df)} merchants={len(merchants_df)} devices={len(devices_df)}")

# ---------------------------------------------------------------------------
# Transactions + ip_events + disputes
# ---------------------------------------------------------------------------
print("Generating transactions with fraud patterns...")

transactions = []
ip_events = []
disputes = []
txn_counter = 0
ip_counter = 0
disp_counter = 0

customer_ids = list(customers_df["id"])
merchant_ids = list(merchants_df["id"])
customers_by_id = customers_df.set_index("id").to_dict("index")
merchants_by_id = merchants_df.set_index("id").to_dict("index")

FRAUD_TYPES = [
    "account_takeover", "fraud_ring", "velocity_attack", "unusual_amount",
    "new_device", "impossible_travel", "shared_ip_device", "card_testing",
]
# Target ~6% overall fraud rate across patterns
TARGET_FRAUD_TXNS = int(N_TRANSACTIONS * 0.06)


def new_txn_id():
    global txn_counter
    tid = f"txn_{txn_counter:07d}"
    txn_counter += 1
    return tid


def add_ip_event(customer_id, txn_id, ip, city, lat, lon, vpn=False, proxy=False, when=None):
    global ip_counter
    ip_events.append({
        "id": f"ipev_{ip_counter:07d}",
        "customer_id": customer_id,
        "transaction_id": txn_id,
        "ip_address": ip,
        "ip_country": "IN" if city not in [c[0] for c in FOREIGN_CITIES] else "XX",
        "city": city,
        "lat": lat,
        "lon": lon,
        "is_vpn": vpn,
        "is_proxy": proxy,
        "event_at": when or NOW,
    })
    ip_counter += 1


def random_ip():
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def make_legit_txn(cid):
    """A normal, non-fraud transaction consistent with the customer's home city."""
    cust = customers_by_id[cid]
    city_match = [c for c in CITIES if c[0] == cust["city"]]
    city, state, lat, lon = city_match[0] if city_match else random.choice(CITIES)
    mid = random.choice(merchant_ids)
    merch = merchants_by_id[mid]
    dev_list = customer_devices.get(cid, [])
    device_id = random.choice(dev_list) if dev_list else None
    amount = max(50, round(np.random.gamma(2.0, merch["avg_ticket_size"] / 3 + 200), 2))
    when = rand_time_between(START, NOW)
    ip = random_ip()
    tid = new_txn_id()
    transactions.append({
        "id": tid, "customer_id": cid, "merchant_id": mid, "device_id": device_id,
        "amount": amount, "currency": "INR", "channel": random.choice(CHANNELS),
        "status": "success", "txn_lat": lat + np.random.normal(0, 0.03),
        "txn_lon": lon + np.random.normal(0, 0.03), "txn_city": city, "txn_country": "IN",
        "ip_address": ip, "created_at": when, "fraud_label": 0, "fraud_type": "none",
    })
    add_ip_event(cid, tid, ip, city, lat, lon, when=when)
    return tid


# --- 1) Bulk legitimate transactions ---------------------------------------
n_legit = N_TRANSACTIONS - TARGET_FRAUD_TXNS
print(f"  generating {n_legit} legitimate transactions...")
legit_customers = np.random.choice(customer_ids, size=n_legit, replace=True)
for cid in legit_customers:
    make_legit_txn(cid)

# --- 2) Fraud pattern injectors ---------------------------------------------

def pattern_account_takeover(n_cases=350):
    for _ in range(n_cases):
        cid = random.choice(customer_ids)
        cust = customers_by_id[cid]
        # attacker uses a brand-new device + foreign/far IP, then drains funds
        when = rand_time_between(START, NOW)
        f_city, f_country, f_lat, f_lon = random.choice(FOREIGN_CITIES)
        mid = random.choice(merchant_ids)
        amount = round(np.random.uniform(15000, 95000), 2)
        tid = new_txn_id()
        ip = random_ip()
        transactions.append({
            "id": tid, "customer_id": cid, "merchant_id": mid, "device_id": None,
            "amount": amount, "currency": "INR", "channel": random.choice(["card", "netbanking"]),
            "status": "success", "txn_lat": f_lat, "txn_lon": f_lon, "txn_city": f_city,
            "txn_country": "XX", "ip_address": ip, "created_at": when,
            "fraud_label": 1, "fraud_type": "account_takeover",
        })
        add_ip_event(cid, tid, ip, f_city, f_lat, f_lon, vpn=True, when=when)
        # a couple of quick follow-up drains
        for _ in range(random.randint(1, 2)):
            when2 = when + dt.timedelta(minutes=random.randint(2, 20))
            tid2 = new_txn_id()
            transactions.append({
                "id": tid2, "customer_id": cid, "merchant_id": random.choice(merchant_ids),
                "device_id": None, "amount": round(np.random.uniform(5000, 40000), 2),
                "currency": "INR", "channel": "netbanking", "status": "success",
                "txn_lat": f_lat, "txn_lon": f_lon, "txn_city": f_city, "txn_country": "XX",
                "ip_address": ip, "created_at": when2, "fraud_label": 1,
                "fraud_type": "account_takeover",
            })


def pattern_fraud_ring(n_rings=40, ring_size_range=(4, 9)):
    for _ in range(n_rings):
        ring_customers = random.sample(customer_ids, k=random.randint(*ring_size_range))
        shared_ip = random_ip()
        shared_device_fp = uuid.uuid4().hex[:16]
        shared_dev_id = f"dev_ring_{uuid.uuid4().hex[:8]}"
        devices.append({
            "id": shared_dev_id, "customer_id": ring_customers[0],
            "device_fingerprint": shared_device_fp, "device_type": "mobile",
            "os": "Android", "first_seen_at": NOW - dt.timedelta(days=5),
            "last_seen_at": NOW, "is_trusted": False,
        })
        mid = random.choice(merchant_ids)  # ring cashes out through shared merchant(s)
        base_when = rand_time_between(START, NOW - dt.timedelta(hours=2))
        for cid in ring_customers:
            when = base_when + dt.timedelta(minutes=random.randint(0, 90))
            amount = round(np.random.uniform(2000, 20000), 2)
            tid = new_txn_id()
            city, _, lat, lon = random.choice(CITIES)
            transactions.append({
                "id": tid, "customer_id": cid, "merchant_id": mid, "device_id": shared_dev_id,
                "amount": amount, "currency": "INR", "channel": "upi", "status": "success",
                "txn_lat": lat, "txn_lon": lon, "txn_city": city, "txn_country": "IN",
                "ip_address": shared_ip, "created_at": when, "fraud_label": 1,
                "fraud_type": "fraud_ring",
            })
            add_ip_event(cid, tid, shared_ip, city, lat, lon, when=when)


def pattern_velocity_attack(n_cases=250):
    for _ in range(n_cases):
        cid = random.choice(customer_ids)
        dev_list = customer_devices.get(cid, [])
        device_id = random.choice(dev_list) if dev_list else None
        base_when = rand_time_between(START, NOW - dt.timedelta(hours=1))
        n_burst = random.randint(6, 15)
        city, _, lat, lon = random.choice(CITIES)
        ip = random_ip()
        for k in range(n_burst):
            when = base_when + dt.timedelta(seconds=random.randint(5, 240) * (k + 1))
            tid = new_txn_id()
            transactions.append({
                "id": tid, "customer_id": cid, "merchant_id": random.choice(merchant_ids),
                "device_id": device_id, "amount": round(np.random.uniform(500, 8000), 2),
                "currency": "INR", "channel": "card", "status": "success",
                "txn_lat": lat, "txn_lon": lon, "txn_city": city, "txn_country": "IN",
                "ip_address": ip, "created_at": when, "fraud_label": 1,
                "fraud_type": "velocity_attack",
            })


def pattern_unusual_amount(n_cases=300):
    for _ in range(n_cases):
        cid = random.choice(customer_ids)
        cust = customers_by_id[cid]
        city_match = [c for c in CITIES if c[0] == cust["city"]]
        city, state, lat, lon = city_match[0] if city_match else random.choice(CITIES)
        dev_list = customer_devices.get(cid, [])
        device_id = random.choice(dev_list) if dev_list else None
        amount = round(np.random.uniform(80000, 300000), 2)  # far above typical spend
        when = rand_time_between(START, NOW)
        tid = new_txn_id()
        ip = random_ip()
        transactions.append({
            "id": tid, "customer_id": cid, "merchant_id": random.choice(merchant_ids),
            "device_id": device_id, "amount": amount, "currency": "INR",
            "channel": random.choice(["card", "netbanking"]), "status": "success",
            "txn_lat": lat, "txn_lon": lon, "txn_city": city, "txn_country": "IN",
            "ip_address": ip, "created_at": when, "fraud_label": 1,
            "fraud_type": "unusual_amount",
        })
        add_ip_event(cid, tid, ip, city, lat, lon, when=when)


def pattern_new_device(n_cases=300):
    for _ in range(n_cases):
        cid = random.choice(customer_ids)
        cust = customers_by_id[cid]
        city_match = [c for c in CITIES if c[0] == cust["city"]]
        city, state, lat, lon = city_match[0] if city_match else random.choice(CITIES)
        when = rand_time_between(START, NOW)
        amount = round(np.random.uniform(3000, 60000), 2)
        tid = new_txn_id()
        ip = random_ip()
        transactions.append({
            "id": tid, "customer_id": cid, "merchant_id": random.choice(merchant_ids),
            "device_id": None,  # unseen / new device -> null link, flagged by device agent
            "amount": amount, "currency": "INR", "channel": random.choice(CHANNELS),
            "status": "success", "txn_lat": lat, "txn_lon": lon, "txn_city": city,
            "txn_country": "IN", "ip_address": ip, "created_at": when,
            "fraud_label": 1, "fraud_type": "new_device",
        })
        add_ip_event(cid, tid, ip, city, lat, lon, when=when)


def pattern_impossible_travel(n_cases=250):
    for _ in range(n_cases):
        cid = random.choice(customer_ids)
        city_a, _, lat_a, lon_a = random.choice(CITIES)
        city_b, _, lat_b, lon_b = random.choice([c for c in CITIES if c[0] != city_a])
        distance = haversine_km(lat_a, lon_a, lat_b, lon_b)
        base_when = rand_time_between(START, NOW - dt.timedelta(hours=1))
        gap_minutes = random.randint(10, 45)  # not enough time to physically travel
        when2 = base_when + dt.timedelta(minutes=gap_minutes)
        dev_list = customer_devices.get(cid, [])
        device_id = random.choice(dev_list) if dev_list else None
        for (city, lat, lon, when) in [(city_a, lat_a, lon_a, base_when), (city_b, lat_b, lon_b, when2)]:
            tid = new_txn_id()
            ip = random_ip()
            transactions.append({
                "id": tid, "customer_id": cid, "merchant_id": random.choice(merchant_ids),
                "device_id": device_id, "amount": round(np.random.uniform(1500, 30000), 2),
                "currency": "INR", "channel": "card", "status": "success",
                "txn_lat": lat, "txn_lon": lon, "txn_city": city, "txn_country": "IN",
                "ip_address": ip, "created_at": when, "fraud_label": 1,
                "fraud_type": "impossible_travel",
            })
            add_ip_event(cid, tid, ip, city, lat, lon, when=when)


def pattern_shared_ip_device(n_groups=60, group_size_range=(3, 6)):
    for _ in range(n_groups):
        group = random.sample(customer_ids, k=random.randint(*group_size_range))
        shared_ip = random_ip()
        shared_dev_id = f"dev_shared_{uuid.uuid4().hex[:8]}"
        devices.append({
            "id": shared_dev_id, "customer_id": group[0], "device_fingerprint": uuid.uuid4().hex[:16],
            "device_type": "mobile", "os": "Android", "first_seen_at": NOW - dt.timedelta(days=2),
            "last_seen_at": NOW, "is_trusted": False,
        })
        city, _, lat, lon = random.choice(CITIES)
        base_when = rand_time_between(START, NOW - dt.timedelta(hours=3))
        for cid in group:
            when = base_when + dt.timedelta(minutes=random.randint(0, 180))
            tid = new_txn_id()
            transactions.append({
                "id": tid, "customer_id": cid, "merchant_id": random.choice(merchant_ids),
                "device_id": shared_dev_id, "amount": round(np.random.uniform(1000, 25000), 2),
                "currency": "INR", "channel": "wallet", "status": "success",
                "txn_lat": lat, "txn_lon": lon, "txn_city": city, "txn_country": "IN",
                "ip_address": shared_ip, "created_at": when, "fraud_label": 1,
                "fraud_type": "shared_ip_device",
            })
            add_ip_event(cid, tid, shared_ip, city, lat, lon, when=when)


def pattern_card_testing(n_cases=200):
    """Multiple small failed authorizations followed by a successful larger charge."""
    for _ in range(n_cases):
        cid = random.choice(customer_ids)
        city, _, lat, lon = random.choice(CITIES)
        ip = random_ip()
        base_when = rand_time_between(START, NOW - dt.timedelta(hours=1))
        n_fail = random.randint(3, 8)
        for k in range(n_fail):
            when = base_when + dt.timedelta(seconds=random.randint(10, 60) * (k + 1))
            tid = new_txn_id()
            transactions.append({
                "id": tid, "customer_id": cid, "merchant_id": random.choice(merchant_ids),
                "device_id": None, "amount": round(np.random.uniform(10, 100), 2),
                "currency": "INR", "channel": "card", "status": "failed",
                "txn_lat": lat, "txn_lon": lon, "txn_city": city, "txn_country": "IN",
                "ip_address": ip, "created_at": when, "fraud_label": 1,
                "fraud_type": "card_testing",
            })
        when_success = base_when + dt.timedelta(minutes=random.randint(5, 15))
        tid = new_txn_id()
        transactions.append({
            "id": tid, "customer_id": cid, "merchant_id": random.choice(merchant_ids),
            "device_id": None, "amount": round(np.random.uniform(20000, 70000), 2),
            "currency": "INR", "channel": "card", "status": "success",
            "txn_lat": lat, "txn_lon": lon, "txn_city": city, "txn_country": "IN",
            "ip_address": ip, "created_at": when_success, "fraud_label": 1,
            "fraud_type": "card_testing",
        })
        add_ip_event(cid, tid, ip, city, lat, lon, when=when_success)


print("  injecting: account takeover")
pattern_account_takeover()
print("  injecting: fraud ring")
pattern_fraud_ring()
print("  injecting: velocity attack")
pattern_velocity_attack()
print("  injecting: unusual amount")
pattern_unusual_amount()
print("  injecting: new device")
pattern_new_device()
print("  injecting: impossible travel")
pattern_impossible_travel()
print("  injecting: shared ip/device")
pattern_shared_ip_device()
print("  injecting: card testing (failed -> successful)")
pattern_card_testing()

transactions_df = pd.DataFrame(transactions)
# Trim/pad to exactly N_TRANSACTIONS by sampling extra legit txns if needed
if len(transactions_df) < N_TRANSACTIONS:
    deficit = N_TRANSACTIONS - len(transactions_df)
    print(f"  topping up {deficit} legitimate transactions to reach target count...")
    for cid in np.random.choice(customer_ids, size=deficit, replace=True):
        make_legit_txn(cid)
    transactions_df = pd.DataFrame(transactions)
elif len(transactions_df) > N_TRANSACTIONS:
    transactions_df = transactions_df.sample(n=N_TRANSACTIONS, random_state=SEED).reset_index(drop=True)

devices_df = pd.DataFrame(devices)  # re-materialize (ring/shared devices appended)
ip_events_df = pd.DataFrame(ip_events)

# ---------------------------------------------------------------------------
# Disputes: filed for a subset of fraud transactions + a few false-positive-style
# disputes on legitimate ones (real-world noise)
# ---------------------------------------------------------------------------
print("Generating disputes...")
fraud_txns = transactions_df[transactions_df["fraud_label"] == 1].sample(
    frac=0.35, random_state=SEED
)
legit_txns_sample = transactions_df[transactions_df["fraud_label"] == 0].sample(
    n=min(500, (transactions_df["fraud_label"] == 0).sum()), random_state=SEED
)
disp_reasons_fraud = ["unauthorized_transaction", "account_compromised", "did_not_receive_goods"]
disp_reasons_legit = ["duplicate_charge", "billing_error", "changed_mind"]

for _, row in fraud_txns.iterrows():
    disputes.append({
        "id": f"disp_{disp_counter:06d}", "transaction_id": row["id"], "customer_id": row["customer_id"],
        "reason": random.choice(disp_reasons_fraud), "status": random.choice(["open", "resolved"]),
        "filed_at": row["created_at"] + dt.timedelta(hours=random.randint(1, 72)),
        "resolved_at": None,
    })
    disp_counter += 1

for _, row in legit_txns_sample.iterrows():
    disputes.append({
        "id": f"disp_{disp_counter:06d}", "transaction_id": row["id"], "customer_id": row["customer_id"],
        "reason": random.choice(disp_reasons_legit), "status": "resolved",
        "filed_at": row["created_at"] + dt.timedelta(hours=random.randint(1, 72)),
        "resolved_at": row["created_at"] + dt.timedelta(days=random.randint(1, 10)),
    })
    disp_counter += 1

disputes_df = pd.DataFrame(disputes)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
print("Writing CSVs...")
customers_df.to_csv(os.path.join(OUT_DIR, "customers.csv"), index=False)
merchants_df.to_csv(os.path.join(OUT_DIR, "merchants.csv"), index=False)
devices_df.to_csv(os.path.join(OUT_DIR, "devices.csv"), index=False)
transactions_df.to_csv(os.path.join(OUT_DIR, "transactions.csv"), index=False)
ip_events_df.to_csv(os.path.join(OUT_DIR, "ip_events.csv"), index=False)
disputes_df.to_csv(os.path.join(OUT_DIR, "disputes.csv"), index=False)

print("\nDone.")
print(f"customers:    {len(customers_df):>7}")
print(f"merchants:    {len(merchants_df):>7}")
print(f"devices:      {len(devices_df):>7}")
print(f"transactions: {len(transactions_df):>7}  (fraud={transactions_df['fraud_label'].sum()}, "
      f"rate={transactions_df['fraud_label'].mean():.4f})")
print(f"ip_events:    {len(ip_events_df):>7}")
print(f"disputes:     {len(disputes_df):>7}")
print("\nFraud type breakdown:")
print(transactions_df[transactions_df.fraud_label == 1]["fraud_type"].value_counts())
