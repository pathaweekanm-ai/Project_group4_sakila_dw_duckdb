---
title: "Sakila DVD Rental Data Warehouse"
---

# Sakila DVD Rental — OLTP to OLAP Data Warehouse

โครงงานนี้จัดทำขึ้นเพื่อออกแบบและพัฒนา Data Warehouse จากฐานข้อมูล Sakila ซึ่งเป็นฐานข้อมูลจำลองธุรกิจร้านเช่าภาพยนตร์ นำข้อมูลมาวิเคราะห์ในมุมมองทางธุรกิจ เช่น แนวโน้มรายได้ ประสิทธิภาพของแต่ละสาขา และพฤติกรรมการเช่าของลูกค้า โครงงานจึงมุ่งเน้นการนำข้อมูลจากระบบฐานข้อมูลเดิมมาจัดโครงสร้างใหม่ในรูปแบบ Data Warehouse เพื่อให้สามารถวิเคราะห์ข้อมูลและตอบคำถามทางธุรกิจได้อย่างสะดวก รวดเร็ว และมีประสิทธิภาพมากยิ่งขึ้น

Database: <https://www.kaggle.com/datasets/atanaskanev/sqlite-sakila-sample-database?select=sqlite-sakila.db>

---

## 1. Operational Database

**ชุดข้อมูล:** Sakila Sample Database (DVD Rental) — โฟลเดอร์ `raw_data_DVD`, ไฟล์ CSV 16 ตาราง

**ขอบเขตข้อมูล:** รายการเช่า (`rental`) ตั้งแต่ 2005-05-24 ถึง 2006-02-14 (~9 เดือน), 2 สาขา, 2 พนักงาน, ลูกค้า 599 คน, หนัง 1,000 เรื่อง, การเช่า 16,044 รายการ, การชำระเงิน 16,049 รายการ

| ตาราง | จำนวนแถว | หมายเหตุ |
|---|---:|---|
| `actor` | 200 | |
| `address` | 603 | |
| `category` | 16 | |
| `city` | 600 | |
| `country` | 109 | |
| `customer` | 599 | |
| `film` | 1,000 | ทุกเรื่องเป็นภาษา English (`language_id = 1`) |
| `film_actor` | 5,462 | bridge ตาราง many-to-many (นักแสดง ↔ หนัง) |
| `film_category` | 1,000 | bridge ตาราง (หนัง ↔ หมวดหนัง) |
| `film_text` | 0 | ว่างเปล่าในชุดข้อมูลนี้ — ไม่ใช้งาน |
| `inventory` | 4,581 | สต๊อกหนังต่อสาขา |
| `language` | 6 | มีแค่ `id=1` (English) ที่ถูกใช้จริงใน `film` |
| `payment` | 16,049 | |
| `rental` | 16,044 | มี `return_date` เป็น `NULL` อยู่ 183 แถว (ยังไม่คืน) |
| `staff` | 2 | |
| `store` | 2 | |

**ER Diagram:**

<img width="5334" height="3000" alt="er_diagram-1" src="https://github.com/user-attachments/assets/34f59cf8-3229-4010-b81b-c84508be7c88" />


---

## 2. Business Questions

### หมวด 1 — รายได้และผลประกอบการ (3 ข้อ)

| # | คำถาม | ตารางต้นทางที่เกี่ยวข้อง | 
|---|---|---|
| BQ01 | รายได้รวมต่อเดือนมีแนวโน้มอย่างไร | payment | 
| BQ02 | สาขาไหนทำรายได้สูงสุด และต่างกันเท่าไร | payment → staff/rental → inventory → store | 
| BQ03 | พนักงานคนไหนสร้างรายได้เข้าร้านมากที่สุด | payment.staff_id | 

### หมวด 2 — พฤติกรรมและมูลค่าลูกค้า (3 ข้อ)

| # | คำถาม | ตารางต้นทางที่เกี่ยวข้อง | 
|---|---|---|
| BQ04 | ลูกค้าจากประเทศไหนมีการใช้จ่ายสูงสุด | payment → customer → address → city → country | 
| BQ05 | Top 10 ลูกค้าที่มียอดใช้จ่ายสะสมมากที่สุด | payment → customer | 
| BQ06 | อัตราลูกค้ากลับมาซื้อซ้ำคิดเป็นเท่าไร | rental → customer | 

### หมวด 3 — ประสิทธิภาพสินค้า (หนัง/หมวดหนัง) (2 ข้อ)

| # | คำถาม | ตารางต้นทางที่เกี่ยวข้อง | 
|---|---|---|
| BQ07 | หมวดหนังไหนถูกเช่าบ่อยที่สุดและทำรายได้สูงสุด | rental → inventory → film_category → category | 
| BQ08 | ความยาวหนังหรือเรตของหนังมีผลต่อความถี่การเช่าไหม | rental → inventory → film | 

### หมวด 4 — สินค้าคงคลัง (Inventory) และการดำเนินงาน (3 ข้อ)

| # | คำถาม | ตารางต้นทางที่เกี่ยวข้อง | 
|---|---|---|
| BQ09 | อัตราการใช้งานสินค้าคงคลังต่อสาขาเป็นอย่างไร | inventory (stock) เทียบกับ rental (การเช่าจริง) ต่อ store | 
| BQ10 | หนังเรื่องไหนมีสต๊อกไม่เพียงพอเทียบกับความต้องการเช่า | inventory (COUNT ต่อ film) vs rental (ความถี่เช่าต่อ film) | 
| BQ11 | ระยะเวลาเช่าเฉลี่ยเทียบกับที่กำหนดไว้ต่างกันแค่ไหน | rental (return_date − rental_date) เทียบกับ film.rental_duration | 

### หมวด 5 — นักแสดงและเนื้อหา (1 ข้อ)

| # | คำถาม | ตารางต้นทางที่เกี่ยวข้อง | 
|---|---|---|
| BQ12 | นักแสดงคนไหนปรากฏในหนังที่ทำรายได้รวมสูงสุด | film_actor → actor join กับรายได้ต่อ film จาก rental + payment |

### หมวด 6 — ฤดูกาลและเวลา (3 ข้อ)

| # | คำถาม | ตารางต้นทางที่เกี่ยวข้อง | 
|---|---|---|
| BQ13 | วันในสัปดาห์ไหนมีการเช่าสูงสุด | rental.rental_date | 
| BQ14 | ช่วงเดือนไหนของปีมีรายได้สูงและต่ำที่สุด | payment.payment_date | 
| BQ15 | วันเช่าเป็นวันธรรมดาหรือวันหยุด มีผลต่อระยะเวลาที่ลูกค้าเก็บหนังไว้ไหม | payment join rental | 


---

## 3. Multidimensional Data Model Design

### 1. Grain (นิยามว่า 1 แถวในตารางคืออะไร)

> **Grain ของ Fact_Rental = 1 แถวต่อ 1 รายการเช่า 1 ครั้ง (1 Rental Transaction)**

กำหนด Grain ในระดับ 1 รายการเช่าต่อ 1 ครั้ง เนื่องจากคำถามทางธุรกิจส่วนใหญ่ใน `business_questions.md` ได้แก่ BQ01–BQ08, BQ11 และ BQ13–BQ15 ต้องการวิเคราะห์ข้อมูลในระดับรายละเอียดของการเช่า หากกำหนด Grain ในระดับที่หยาบกว่า เช่น 1 แถวต่อวันต่อสาขา จะไม่สามารถตอบคำถามเชิงลึกในระดับลูกค้าหรือภาพยนตร์แต่ละเรื่องได้อย่างเหมาะสม

ตารางต้นทางที่ใช้กำหนด Grain คือ rental โดยข้อมูล 1 แถวแทนการเช่า 1 ครั้ง และมี `rental_id` เป็น Primary Key สำหรับข้อมูลการชำระเงิน ตาราง payment มีความสัมพันธ์กับรายการเช่า โดยข้อมูลส่วนใหญ่สามารถเชื่อมโยงกับการเช่าแต่ละครั้งได้ จึงนำข้อมูลการชำระเงินที่เกี่ยวข้องมาใช้เป็นส่วนหนึ่งของ `Fact_Rental` แทนการสร้าง `Fact_Payment` แยกต่างหาก

นอกจากนี้ **มีการออกแบบ Fact Table ตัวที่สอง** สำหรับตอบคำถาม BQ09–BQ10 ซึ่งเกี่ยวข้องกับ Inventory Utilization และ Stock Shortage เนื่องจากลักษณะและระดับรายละเอียดของข้อมูล (Grain) แตกต่างจากข้อมูลการเช่า จึงควรแยกออกเป็น Fact Table ต่างหาก

---

### 2. Dimension ทั้งหมดและระดับ (Level)

| Dimension | Level (จากละเอียด → หยาบ) | Attribute หลัก | มาจากตาราง staging |
|---|---|---|---|
| **Dim_Date** | วัน → สัปดาห์ → เดือน → ไตรมาส → ปี | `full_date`, `day_of_week_name`, `is_weekend`, `week_of_year`, `month_name`, `quarter`, `year` | generate เอง |
| **Dim_Customer** | ลูกค้า → เมือง → ประเทศ | `full_name`, `email`, `city`, `country`, `active_flag`, `home_store_id` | `stg_customer`, `stg_address`, `stg_city`, `stg_country` |
| **Dim_Film** | เรื่อง → หมวดหนัง (category) → เรตติ้ง | `title`, `category`, `rating`, `length`, `rental_duration`, `rental_rate`, `release_year` | `stg_film`, `stg_film_category`, `stg_category`  |
| **Dim_Store** | สาขา → เมือง → ประเทศ | `address`, `city`, `country`, `manager_name` | `stg_store`, `stg_staff (ผู้จัดการ)`, `stg_address`, `stg_city`, `stg_country` |
| **Dim_Staff** | พนักงาน → สาขาที่สังกัด | `full_name`, `store_id` | `stg_staff` |
| **Dim_Actor** | นักแสดง | `first_name`, `last_name` | `stg_actor`  |

**Dim_Date เป็น Role-Playing Dimension**  โดยใช้ตารางเดียวกันสำหรับวันที่เช่า (`rental_date_key`) วันที่คืน (`return_date_key`) และวันที่ชำระเงิน (`payment_date_key`) โดย Join ตาราง `Dim_Date` ด้วย Alias ที่แตกต่างกัน ไม่จำเป็นต้องสร้างตารางวันที่ 3 ตาราง

**Dim_Film เลือกใช้ Star Schema** โดยรวมข้อมูล Category และ Language ไว้ใน `Dim_Film` เพื่อให้โครงสร้างไม่ซับซ้อนและ Query ได้ง่าย เนื่องจากข้อมูลมีเพียง 16 หมวดหมู่และ 1 ภาษา จึงไม่จำเป็นต้องแยกเป็น Snowflake Schema

---
### 3. Fact Table และ Measure

#### Fact_Rental (Main Fact)

| Measure | สูตร/ที่มา | ประเภท | หมายเหตุ |
|---|---|---|---|
| `rental_count` | = 1 ทุกแถว | **Additive** | นับจำนวนการเช่า |
| `payment_amount` | `payment.amount` | **Additive** | ใช้คำนวณรายได้ |
| `rental_duration_actual_days` | `return_date − rental_date` | **ใช้ AVG เป็นหลัก** | วิเคราะห์ระยะเวลาการเช่า |
| `days_late` | ระยะเวลาเช่าจริง − ระยะเวลาที่กำหนด | **ใช้ AVG เป็นหลัก** | วิเคราะห์การคืนล่าช้า |
| `payment_lag_days` | `payment_date − rental_date` | **ใช้ AVG เป็นหลัก** | วิเคราะห์ระยะเวลาการชำระเงิน |
| `is_returned` | 1 = คืนแล้ว, 0 = ยังไม่คืน | **flag** | ใช้กรองและวิเคราะห์สถานะการคืน |

**Foreign Key ที่ต้องมี:** `rental_date_key`, `return_date_key`, `payment_date_key` (→ `Dim_Date` 3 บทบาท), `customer_key` (→ `Dim_Customer`), `film_key` (→ `Dim_Film`), `store_key` (→ `Dim_Store`), และ `staff_key` (→ `Dim_Staff`)

ส่วน `rental_id` และ `inventory_id` เป็น Degenerate Dimension เก็บไว้สำหรับตรวจสอบและเชื่อมโยงกลับไปยังข้อมูลต้นทาง โดยไม่ต้องสร้าง Dimension Table แยก

#### Fact_Inventory ( Fact Table ตัวที่สอง — สำหรับ BQ09, BQ10)

**Grain: 1 แถว ต่อ 1 หนัง ต่อ 1 สาขา** (เป็นข้อมูลระดับสต๊อก ไม่ใช่ระดับธุรกรรม)

| Measure | สูตร/ที่มา | ประเภท |
|---|---|---|
| `inventory_count` | COUNT(`inventory_id`) แยกตามภาพยนตร์และสาขา | **Semi-additive**  |
| `rental_count_to_date` | COUNT(`rental_id`) จาก `Fact_Rental` ตามภาพยนต์และสาขา | **Additive** |
| `utilization_ratio` | `rental_count_to_date / inventory_count` | **Non-additive** |

**หมายเหตุ:** `utilization_ratio` เป็นอัตราส่วน จึงไม่ควรนำมารวม (SUM) หรือเฉลี่ยโดยตรง ควรรวมตัวตั้งและตัวหารก่อน แล้วจึงคำนวณอัตราส่วน
---

### 4. เช็คความครบถ้วน — ทุกคำถามธุรกิจตอบได้จาก 2 fact table นี้

| BQ | ตอบจาก |
|---|---|
| BQ01–BQ03 | `Fact_Rental.payment_amount` + `Dim_Date`/`Dim_Store`/`Dim_Staff` |
| BQ04–BQ06 | `Fact_Rental` + `Dim_Customer` |
| BQ07 | `Fact_Rental` + `Dim_Film` (category) |
| BQ08 | `Fact_Rental` + `Dim_Film` (length, rating) |
| BQ09–BQ10 | `Fact_Inventory` |
| BQ11 | `Fact_Rental.days_late` + `Dim_Film` |
| BQ12 | `Fact_Rental.payment_amount` + `Dim_Film` + `Bridge_Film_Actor` + `Dim_Actor` |
| BQ13–BQ15 | `Fact_Rental` + `Dim_Date` |

---

## 4. Data Model Diagram (Galaxy Schema — ประกอบด้วย Star Schema หลายชุด)

<img width="1582" height="1838" alt="Untitled" src="https://github.com/user-attachments/assets/3d4d21ff-4e66-48cf-82ed-d085e76c3a63" />

<br> มี Fact_Rental เป็น Main Fact และ Fact_Inventory เป็นอีก Fact Table ซึ่งใช้ Dimension บางส่วนร่วมกัน

## 5. ETL / ELT Process

🟢 **Staging layer เสร็จแล้วและรันผ่านจริง** — ดูรายละเอียดได้ที่ [`sakila_dw_duckdb/`](sakila_dw_duckdb/)

- [x] **Extract:** นำข้อมูล CSV ต้นทาง 15 ตารางเข้า DuckDB ด้วย dbt seed (`main_raw`)
- [x] **Clean:** กำหนด Column Type และตรวจเช็กความถูกต้องของข้อมูลเบื้องต้น
- [x] **Transform:** สร้าง Staging Models, เพิ่ม `_loaded_at`, คำนวณ Measure เพิ่มเติม และทำ Snapshot (SCD Type 2)
- [x] **Data Quality:** ผ่านการทดสอบ (เช็ก PK ไม่ซ้ำ/ไม่ว่าง, เช็ก FK ป้องกันข้อมูลกำพร้า และ Singular Test ดักตรรกะผิดปกติ 2 ข้อ)
- [ ] **Load:** โหลดข้อมูลเข้าสู่ Fact และ Dimension Tables ใน Schema `marts` (อยู่ระหว่างดำเนินการ)

## 6. Data Warehouse Database

🟢 **เสร็จแล้ว** — Star Schema เต็มรูปแบบใน DuckDB

* **Database Location:** `sakila_dw_duckdb/sakila_dw.duckdb` (Schema: `main_marts`)
* **Verification:** ตรวจสอบและทดสอบคิวรีแล้วว่าสามารถตอบคำถามธุรกิจได้ครบถ้วน
* **รายละเอียดเพิ่มเติม:** ดูตัวอย่างผลลัพธ์ได้ที่ [`sakila_dw_duckdb/README.md`](sakila_dw_duckdb/README.md)

---

## 7. Interactive Dashboard

🟢 **เสร็จแล้ว** — Streamlit Web Application สำหรับแสดงผลข้อมูล

* **Data Source:** ดึงข้อมูลโดยตรงจาก Schema `main_marts` (Fact & Dimension Tables)
* **Features:** ครอบคลุมคำถามทางธุรกิจทั้ง 15 ข้อ จัดหมวดหมู่การแสดงผลออกเป็น 6 แท็บ
* **Documentation:** ดูวิธีรันและขั้นตอน Deploy ได้ที่ [`dashboard/README.md`](dashboard/README.md)
* **Web Application:** [ลิงก์เข้าใช้งาน Dashboard](https://projectgroup4sakiladwduckdb-3ydsbdb8xgh6wo7433burx.streamlit.app/) *(ใส่หลัง Deploy บน Streamlit Community Cloud)*
## โครงสร้าง Repository

```text
.
├── README.md
├── docs/
│   ├── business_questions.md     # คำถามธุรกิจ 15 ข้อ (ล็อกแล้ว)
│   ├── er_diagram_source.png     # ER Diagram ต้นทาง
│   ├── er_diagram_source.svg
│   └── generate_er_diagram.py   # สคริปต์สร้าง ER Diagram จาก schema
├── sakila_dw_duckdb/             # โปรเจกต์ dbt — staging layer (seed→run→test→snapshot ผ่านแล้ว)
│   └── README.md                 # อธิบายโครงสร้าง dbt project และผลรันล่าสุด
└── dashboard/                    # TODO: ไฟล์/ลิงก์ที่เกี่ยวกับแดชบอร์ด
```
---

## Team Contribution

> 🚧 ยังไม่เริ่ม — จะอ้างอิงจาก GitHub Project board และ commit history เมื่อทีมเริ่มทำงานจริง

---

## สมาชิก STAT
| รหัสนักศึกษา | ชื่อ | 
|---|---|
|663020034-3|นางสาวสุพิชตรา ภาเฮียง|  
|	663020261-2|นางสาวธีรนาฏ ขอร่ม| 
|	663020267-0|นางสาวมณีรัตน์ เอชัยภูมิ| 
|663020270-1|นางสาวศุภนุช วิริยสถิตย์กุล| 
|	663020275-1|นางสาวเนตรทิพย์ พรหมสิทธิ| 
|	663020568-6|นางสาวกัญญาณัฐ บุษมงคล| 
|663020575-9|นายปทวีกรานต์ มีพรหม| 
