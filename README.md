# gq-transit-infra

**Guinea Ecuatorial Public Transit System — Infrastructure & Operations**

Master repository for the GQ Transit platform. Contains shared scripts, network documentation, database management, and province-level configuration for the national deployment.

---

## Repository map

| Repository | Purpose | Deploy to |
|-----------|---------|-----------|
| [gq-transit-bus](https://github.com/YOUR_USERNAME/gq-transit-bus) | Pi 3 software for each bus | Every bus |
| [gq-transit-server](https://github.com/YOUR_USERNAME/gq-transit-server) | City Hall Flask+MariaDB server | Malabo + Bata |
| [gq-transit-relay](https://github.com/YOUR_USERNAME/gq-transit-relay) | District relay node software | Each terminal |
| **gq-transit-infra** (this repo) | Infra scripts, network plan, DB setup | Ops / admin |
| [gq-transit-docs](https://github.com/YOUR_USERNAME/gq-transit-docs) | Presentation, dossier, deployment guide | Stakeholders |

---

## National deployment overview

### Bioko Island (Phase 1 — Malabo server)
```
Malabo server (10.10.0.1)
  └── bus_tracking_gq_bioko
  └── Relay nodes: Luba, Riaba, Moka, Punta Europa
  └── ~55 buses, 9 routes
```

### Rio Muni (Phase 2 — Bata server)
```
Bata server (10.20.0.1)
  ├── bus_tracking_gq_litoral        (Bata metro)
  ├── bus_tracking_gq_centrosur      (Ebolowa corridor)
  ├── bus_tracking_gq_welenzas       (Mongomo, Evinayong)
  ├── bus_tracking_gq_kientem        (Ebibeyin, Nsork)
  └── bus_tracking_gq_interprovince  (cross-province Greyhound routes)
```

### Key design decision: separate databases per province

Each province database is **independent**. If the WAN link between Malabo and Bata fails, both servers keep running for their local regions. Buses always report to the server of their current region, determined by which relay node's WiFi they connect to.

Cross-province buses (e.g. Bata → Ebibeyin) write to `bus_tracking_gq_interprovince`. Their relay nodes at each province boundary write arrival events to both the local province DB and the interprovince DB, giving a unified picture of the full journey.

---

## Setting up a new region

```bash
# 1. Create the province database
python scripts/setup_region_database.py --region litoral \
  --host 10.20.0.1 --user root --password your_root_password

# 2. Import stops for this province
# (prepare a CSV with columns: name, lat, lng)
python src/admin_cli.py --region Litoral import-stops data/stops_litoral.csv

# 3. Add routes
python src/admin_cli.py --region Litoral add-route \
  --id BL01 --client TRANSLIT --type 1 \
  --stops "Terminal Central Bata,Mercado Bata,Hospital General Bata,Aeropuerto Bata"

# 4. Deploy relay nodes in Litoral using gq-transit-relay
# (same installer, set CITYHAL_IP=10.20.0.1 and BUS_SUBNET=10.20.1)

# 5. Install buses using gq-transit-bus
# (set REGION_NAME=Litoral and SERVER_URL=http://bata-server:5000 in .env)
```

---

## Cross-province routes (Greyhound buses)

For a bus running Bata (Litoral) → Ebibeyin (Kie-Ntem):

1. Bus `.env`: `REGION_NAME=IntreProvince`
2. Relay nodes in Litoral, Wele-Nzas, and Kie-Ntem all write to `bus_tracking_gq_interprovince`
3. ETA engine queries interprovince DB for cross-boundary routes
4. Passenger map shows the bus throughout the entire journey regardless of which province it's in

---

## Network IP plan

### Bioko backbone (10.10.0.0/16)
| Device | IP |
|--------|-----|
| Malabo server | 10.10.0.1 |
| Relay Luba | 10.10.1.1 |
| Relay Riaba | 10.10.2.1 |
| Relay Moka | 10.10.3.1 |
| Relay Punta Europa | 10.10.4.1 |

### Rio Muni backbone (10.20.0.0/16)
| Device | IP |
|--------|-----|
| Bata server | 10.20.0.1 |
| Relay Mongomo (Wele-Nzas) | 10.20.1.1 |
| Relay Evinayong (Centro Sur) | 10.20.2.1 |
| Relay Ebibeyin (Kie-Ntem) | 10.20.3.1 |
| Relay Nsork (Kie-Ntem) | 10.20.4.1 |
| Additional nodes TBD | 10.20.5–9.1 |

### Cross-province bus routing
Buses automatically connect to whichever `BIOKO_BUS` access point is in range. The relay node's dnsmasq resolves `bioko-server` to the nearest server (Malabo or Bata) based on which backbone network the relay is on.

---

## Disaster recovery

All province databases are independent — no single point of failure for operations.

| Failure | Impact | Recovery |
|---------|--------|----------|
| Malabo WAN down | Bioko continues normally; Rio Muni unaffected | Automatic |
| Bata WAN down | Rio Muni continues normally; Bioko unaffected | Automatic |
| Relay node down | Buses at that terminal queue offline; all others unaffected | Replace Pi (~$45) |
| Bus Pi down | That bus goes offline; all others unaffected | Replace Pi (~$45) |
| City Hall server down | All buses in region queue offline | Restart service or restore from backup |

---

## Scripts reference

| Script | Purpose |
|--------|---------|
| `scripts/setup_region_database.py` | Create or migrate a province database |
| `scripts/backup_database.sh` | Dump all province databases to compressed files |
| `scripts/sync_interprovince.py` | Manual sync trigger between province DBs |

---

## License

MIT — owned by the project owner. See LICENSE.
