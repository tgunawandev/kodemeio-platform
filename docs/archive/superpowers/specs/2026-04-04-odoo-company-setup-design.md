# Odoo Company Setup — Design Spec

**Goal:** Set up CV Mandiri Agro Cemerlang (MAC) end-to-end on `odoo-dist-mac.mandiriagro.com` with multi-OU, multi-warehouse, POS, Indonesian taxes, and full purchase→inventory→sales→accounting flow. Then export as replayable YAML for TPP and future companies.

## Company Profile
- **Name:** CV Mandiri Agro Cemerlang
- **Currency:** IDR
- **Timezone:** Asia/Jakarta
- **Language:** Indonesian (id_ID)
- **Website:** mandiriagro.com
- **Base URL:** https://odoo-dist-mac.mandiriagro.com
- **Fiscal Year:** January–December

## Operating Units (7)
| Code | Name | Type | Has Warehouse? |
|------|------|------|----------------|
| OFC | Office | Admin HQ | No |
| JKT | Jakarta | Regional | Yes (via outlets) |
| BDG | Bandung | Regional | Yes |
| SLO | Solo | Regional | Yes |
| SBY | Surabaya | Regional | Yes |
| MDN | Medan | Regional | Yes (2 outlets) |
| MKS | Makassar | Regional | Yes |

## Warehouses (7 — one per outlet)
| Warehouse | Code | OU | Stock Locations |
|-----------|------|----|----------------|
| Jakarta-01 | JKT01 | Jakarta | Stock/Onion |
| Bandung-01 | BDG01 | Bandung | Stock/Onion |
| Solo-01 | SLO01 | Solo | Stock/Onion |
| Surabaya-01 | SBY01 | Surabaya | Stock/Onion |
| Medan-01 | MDN01 | Medan | Stock/Onion |
| Medan-02 | MDN02 | Medan | Stock/Onion |
| Makassar-01 | MKS01 | Makassar | Stock/Onion |

All warehouses: 1-step receipt, 1-step delivery.

## CRM Teams (7 — one per outlet)
| Team | Warehouse | OU |
|------|-----------|-----|
| Jakarta-01 | JKT01 | Jakarta |
| Bandung-01 | BDG01 | Bandung |
| Solo-01 | SLO01 | Solo |
| Surabaya-01 | SBY01 | Surabaya |
| Medan-01 | MDN01 | Medan |
| Medan-02 | MDN02 | Medan |
| Makassar-01 | MKS01 | Makassar |

## Business Flows
- **Purchase:** Office OU creates PO → supplier delivers to outlet warehouse
- **Receipt:** Outlet warehouse receives goods (1-step)
- **Sales:** Outlet sells via POS or SO, linked to CRM Team
- **Delivery:** From outlet stock (1-step)
- **Accounting:** Centralized at Office OU

## Chart of Accounts & Taxes
- Indonesian PSAK-based CoA (l10n_id)
- PPN Keluaran 11% (output VAT)
- PPN Masukan 11% (input VAT)
- PPh 21 (employee income)
- PPh 23 (services)
- PPh 4(2) (final tax)

## Journals
| Journal | Code | Type |
|---------|------|------|
| Penjualan | SAL | sale |
| Pembelian | PUR | purchase |
| Bank BCA | BCA | bank |
| Bank Mandiri | MDR | bank |
| Kas | CSH | cash |
| Persediaan | STK | general |
| Pajak | TAX | general |

## Payment Terms
- Tunai (Immediate)
- Net 7
- Net 14
- Net 30
- Net 60

## POS Configuration
- One POS config per outlet
- Linked to outlet warehouse + cash journal

## SMTP
- Server: mail.kodeme.io:587 (TLS)
- From: mac@kodeme.io

## Exportable Setup
Export all configuration as YAML files for replay on TPP and future companies.
