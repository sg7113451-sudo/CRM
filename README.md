# Simple CRM (Streamlit + SQLite)

A small CRM to track leads, follow-ups and notes, with a dashboard.

## Features
- **Today:** leads whose follow-up date is today or overdue. Save a note and set the next follow-up in one click.
- **Leads:** search, filter by status, edit, add notes, delete, download CSV.
- **Add lead:** name, phone, email, company, source, deal value, follow-up date.
- **Dashboard:** total/open/won leads, win rate, open pipeline value, charts by status and source.

## Files
| File | Purpose |
|------|---------|
| `app.py` | The screens (Streamlit) |
| `db.py` | The database code (SQLite, no install needed) |
| `requirements.txt` | Packages to install |
| `crm.db` | Created automatically on first run. This is your data. |

## Run it on your computer
1. Install Python 3.10 or newer.
2. Put all the files in one folder and open a terminal in that folder.
3. Install the packages:
   ```
   pip install -r requirements.txt
   ```
4. Start the app:
   ```
   streamlit run app.py
   ```
5. Your browser opens at `http://localhost:8501`. If the database is empty, click **Load demo data** in the sidebar to see how it looks.

## Put it on GitHub (for your portfolio)
Upload `app.py`, `db.py`, `requirements.txt` and this README. Do **not** upload `crm.db` if it has real customer data. Add a line `crm.db` to a `.gitignore` file.

## Important note about free hosting
Streamlit Community Cloud is free, but it can reset files when the app restarts, so `crm.db` may be lost there. Use the hosted version as a demo (with demo data). For real daily use, run it on your own computer, or later move the data to Google Sheets or a cloud database like Supabase.

## Ideas to improve it next
- Login with a password
- Import leads from an Excel/CSV file
- WhatsApp click-to-chat link for each lead
- Monthly report with Power BI connected to the data
