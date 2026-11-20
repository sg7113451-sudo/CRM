"""Simple CRM - Streamlit app.

Run it with:   streamlit run app.py
"""
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import db

st.set_page_config(page_title="Simple CRM", page_icon="📇", layout="wide")
db.init_db()

COLUMN_TITLES = {
    "id": "ID", "name": "Name", "phone": "Phone", "email": "Email",
    "company": "Company", "source": "Source", "status": "Status",
    "value": "Deal value (₹)", "next_followup": "Next follow-up",
    "created_at": "Added on", "days_overdue": "Days overdue",
}


# ---------------------------------------------------------------- helpers
def inr(amount):
    return f"₹{amount:,.0f}"


def flash(message):
    """Keep a message for the next screen refresh (shown once)."""
    st.session_state["flash"] = message


def show_flash():
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


def pretty(df):
    return df.rename(columns=COLUMN_TITLES)


def bar_chart(data, x_title, y_title, order=None):
    """Simple bar chart. `data` is a Series; `order` keeps the x labels in a fixed order."""
    frame = data.rename_axis(x_title).reset_index(name=y_title)
    chart = (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            x=alt.X(f"{x_title}:N", sort=order if order else "-y", title=None,
                    axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{y_title}:Q", title=y_title),
            tooltip=[x_title, y_title],
        )
    )
    st.altair_chart(chart)


# ------------------------------------------------------------------ pages
def page_today():
    st.header("Today's follow-ups")
    show_flash()

    due = db.followups_due()
    if due.empty:
        st.success("No follow-ups due. You are all caught up! 🎉")
        return

    c1, c2 = st.columns(2)
    c1.metric("Follow-ups due", len(due))
    c2.metric("Overdue", int((due["days_overdue"] > 0).sum()))

    columns = ["id", "name", "phone", "company", "status", "next_followup", "days_overdue"]
    st.dataframe(pretty(due[columns]), hide_index=True)

    st.subheader("Update a follow-up")
    names = dict(zip(due["id"].astype(int), due["name"]))
    lead_id = st.selectbox("Lead", list(names), format_func=lambda i: f"{names[i]}  (ID {i})",
                           key="today_lead")

    with st.form("followup_form", clear_on_submit=True):
        note = st.text_area("What happened? (optional note)")
        days = st.number_input("Next follow-up in how many days?", min_value=1,
                               max_value=365, value=3, step=1)
        b1, b2 = st.columns(2)
        schedule = b1.form_submit_button("Save & schedule next follow-up", type="primary")
        stop = b2.form_submit_button("Save & stop follow-ups")

    if schedule or stop:
        if note.strip():
            db.add_note(lead_id, note)
        if schedule:
            db.update_lead(lead_id, next_followup=date.today() + timedelta(days=int(days)))
            flash(f"Saved. Next follow-up for {names[lead_id]} is in {int(days)} day(s).")
        else:
            db.update_lead(lead_id, next_followup=None)
            flash(f"Saved. No more follow-ups for {names[lead_id]}.")
        st.rerun()


def page_leads():
    st.header("Leads")
    show_flash()

    f1, f2 = st.columns([1, 2])
    status = f1.selectbox("Status", ["All"] + db.STATUSES)
    search = f2.text_input("Search (name, phone, email, company)")

    df = db.get_leads(status, search)
    st.caption(f"{len(df)} lead(s)")
    if df.empty:
        st.info("No leads found. Add one from the 'Add lead' page.")
        return

    st.dataframe(pretty(df), hide_index=True)
    # utf-8-sig so Excel shows the ₹ sign and non-English names correctly
    st.download_button("Download as CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="leads.csv", mime="text/csv")

    st.divider()
    edit_section(df)


def edit_section(df):
    st.subheader("Edit a lead")
    names = dict(zip(df["id"].astype(int), df["name"]))
    lead_id = st.selectbox("Choose a lead", list(names),
                           format_func=lambda i: f"{names[i]}  (ID {i})", key="edit_pick")
    lead = db.get_lead(lead_id)
    if lead is None:
        st.warning("This lead no longer exists.")
        return

    with st.form(f"edit_form_{lead_id}"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", lead["name"], key=f"name_{lead_id}")
        phone = c2.text_input("Phone", lead["phone"] or "", key=f"phone_{lead_id}")
        c3, c4 = st.columns(2)
        email = c3.text_input("Email", lead["email"] or "", key=f"email_{lead_id}")
        company = c4.text_input("Company", lead["company"] or "", key=f"company_{lead_id}")
        c5, c6, c7 = st.columns(3)
        source = c5.selectbox("Source", db.SOURCES,
                              index=db.SOURCES.index(lead["source"]) if lead["source"] in db.SOURCES else len(db.SOURCES) - 1,
                              key=f"source_{lead_id}")
        status = c6.selectbox("Status", db.STATUSES, index=db.STATUSES.index(lead["status"]),
                              key=f"status_{lead_id}")
        value = c7.number_input("Deal value (₹)", min_value=0.0, value=float(lead["value"] or 0),
                                step=1000.0, key=f"value_{lead_id}")
        current_fu = (datetime.strptime(lead["next_followup"], "%Y-%m-%d").date()
                      if lead["next_followup"] else None)
        has_fu = st.checkbox("Set a follow-up date", value=current_fu is not None,
                             key=f"hasfu_{lead_id}")
        fu_date = st.date_input("Next follow-up", value=current_fu or date.today() + timedelta(days=1),
                                key=f"fu_{lead_id}")
        save = st.form_submit_button("Save changes", type="primary")

    if save:
        try:
            db.update_lead(lead_id, name=name, phone=phone, email=email, company=company,
                           source=source, status=status, value=value,
                           next_followup=fu_date if has_fu else None)
        except ValueError as error:
            st.error(str(error))
        else:
            flash("Lead updated.")
            st.rerun()

    st.markdown("**Notes**")
    with st.form(f"note_form_{lead_id}", clear_on_submit=True):
        new_note = st.text_area("Add a note (call summary, promise, anything useful)")
        add_note = st.form_submit_button("Add note")
    if add_note:
        try:
            db.add_note(lead_id, new_note)
        except ValueError as error:
            st.error(str(error))
        else:
            flash("Note added.")
            st.rerun()

    notes = db.get_notes(lead_id)
    if notes.empty:
        st.caption("No notes yet.")
    else:
        st.dataframe(notes.rename(columns={"note": "Note", "created_at": "When"})[["When", "Note"]],
                     hide_index=True)

    with st.expander("Delete this lead"):
        sure = st.checkbox("Yes, delete this lead and all its notes", key=f"sure_{lead_id}")
        if st.button("Delete lead", disabled=not sure, key=f"del_{lead_id}"):
            db.delete_lead(lead_id)
            flash("Lead deleted.")
            st.rerun()


def page_add():
    st.header("Add a new lead")
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name *")
        phone = c2.text_input("Phone")
        c3, c4 = st.columns(2)
        email = c3.text_input("Email")
        company = c4.text_input("Company")
        c5, c6 = st.columns(2)
        source = c5.selectbox("Source", db.SOURCES)
        value = c6.number_input("Expected deal value (₹)", min_value=0.0, value=0.0, step=1000.0)
        has_fu = st.checkbox("Set a follow-up date", value=True)
        fu_date = st.date_input("Next follow-up", value=date.today() + timedelta(days=1))
        note = st.text_area("First note (optional)")
        submitted = st.form_submit_button("Add lead", type="primary")

    if submitted:
        try:
            lead_id = db.add_lead(name, phone, email, company, source, "New", value,
                                  fu_date if has_fu else None)
            if note.strip():
                db.add_note(lead_id, note)
        except ValueError as error:
            st.error(str(error))
        else:
            st.success(f"Lead '{name.strip()}' added. Add another one, or open the Leads page.")


def page_dashboard():
    st.header("Dashboard")
    stats = db.get_stats()
    if stats["total"] == 0:
        st.info("No data yet. Add some leads first (or use 'Load demo data' in the sidebar).")
        return

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total leads", stats["total"])
    m2.metric("Open leads", stats["open"])
    m3.metric("Won", stats["won"])
    m4.metric("Win rate", f"{stats['win_rate']:.0f}%", help="Won ÷ (Won + Lost)")
    m5.metric("Open pipeline", inr(stats["pipeline_value"]))
    st.metric("Value of won deals", inr(stats["won_value"]))

    left, right = st.columns(2)
    with left:
        st.subheader("Leads by status")
        bar_chart(stats["by_status"], "Status", "Leads", order=db.STATUSES)
    with right:
        st.subheader("Deal value by status (₹)")
        bar_chart(stats["value_by_status"], "Status", "Value", order=db.STATUSES)

    st.subheader("Where do leads come from?")
    bar_chart(stats["by_source"], "Source", "Leads")


# ------------------------------------------------------------------- main
def main():
    st.sidebar.title("📇 Simple CRM")
    page = st.sidebar.radio("Menu", ["Today", "Leads", "Add lead", "Dashboard"])

    if db.count_leads() == 0:
        st.sidebar.caption("The database is empty.")
        if st.sidebar.button("Load demo data"):
            db.seed_demo()
            st.rerun()

    {"Today": page_today, "Leads": page_leads,
     "Add lead": page_add, "Dashboard": page_dashboard}[page]()


main()
