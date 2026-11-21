import sqlite3
import calendar
from contextlib import closing
from datetime import date, datetime

DB_NAME = "gym.db"

PAYMENT_METHODS = {"1": "Cash", "2": "UPI", "3": "Card", "4": "Online"}




def connect():
    """Open the database (with foreign keys switched on)."""
    con = sqlite3.connect(DB_NAME)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def money(amount):
    """Show an amount nicely, e.g. Rs. 2,700.00"""
    return f"Rs. {amount:,.2f}"


def ask_int(prompt):
    """Keep asking until the person types a whole number."""
    while True:
        text = input(prompt).strip()
        try:
            return int(text)
        except ValueError:
            print("  That doesn't look like a number. Please try again.")


def ask_float(prompt):
    """Keep asking until the person types a valid amount."""
    while True:
        text = input(prompt).strip()
        try:
            return float(text)
        except ValueError:
            print("  That doesn't look like a valid amount. Please try again.")


def confirm(question):
    """Ask a yes/no question. Returns True only for 'y' or 'yes'."""
    answer = input(f"{question} (y/n): ").strip().lower()
    return answer in ("y", "yes")


def valid_phone(text):
    return text.isdigit() and len(text) == 10


def valid_email(text):
    parts = text.split("@")
    return (
        len(parts) == 2
        and parts[0] != ""
        and "." in parts[1]
        and " " not in text
    )


def ask_optional(prompt, is_valid, error_message):
    """
    Ask for something that may be left blank.
    Blank is accepted (returns ""); anything else must pass is_valid.
    """
    while True:
        text = input(prompt).strip()
        if text == "" or is_valid(text):
            return text
        print("  " + error_message)


def choose_payment_method():
    """Show the payment menu. Returns the method name, or None if invalid."""
    print("\nHow is the payment being made?")
    for key, name in PAYMENT_METHODS.items():
        print(f"  {key}. {name}")
    choice = input("Enter your choice: ").strip()
    return PAYMENT_METHODS.get(choice)


def print_table(title, headers, rows):
    """Print rows as a neat table."""
    print(f"\n--- {title} ---")
    if not rows:
        print("Nothing to show yet.")
        return

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len("" if cell is None else str(cell)))

    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("-" * len(header_line))
    for row in rows:
        print(" | ".join(
            ("" if c is None else str(c)).ljust(widths[i])
            for i, c in enumerate(row)
        ))


def add_months(start, months):
    """Add months to a date, handling short months (e.g. Jan 31 + 1 month)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def update_expired():
    """Mark memberships as Expired once their end date has passed."""
    with closing(connect()) as con:
        con.execute(
            """
            UPDATE Memberships SET status = 'Expired'
            WHERE status = 'Active' AND end_date < ?
            """,
            (date.today().isoformat(),),
        )
        con.commit()





def create_tables():
    with closing(connect()) as con:
        cur = con.cursor()

        cur.executescript("""
        CREATE TABLE IF NOT EXISTS Members (
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            phone TEXT UNIQUE,
            email TEXT UNIQUE,
            join_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Membership_Plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name TEXT UNIQUE NOT NULL,
            duration_months INTEGER NOT NULL CHECK(duration_months > 0),
            price REAL NOT NULL CHECK(price >= 0)
        );

        CREATE TABLE IF NOT EXISTS Memberships (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY(member_id) REFERENCES Members(member_id),
            FOREIGN KEY(plan_id) REFERENCES Membership_Plans(plan_id)
        );

        CREATE TABLE IF NOT EXISTS Payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            membership_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            FOREIGN KEY(membership_id) REFERENCES Memberships(membership_id)
        );

        CREATE TABLE IF NOT EXISTS Attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT,
            FOREIGN KEY(member_id) REFERENCES Members(member_id)
        );
        """)

       
        cur.execute("SELECT COUNT(*) FROM Membership_Plans")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                """
                INSERT INTO Membership_Plans (plan_name, duration_months, price)
                VALUES (?, ?, ?)
                """,
                [
                    ("Monthly", 1, 1000),
                    ("Quarterly", 3, 2700),
                    ("Half-Yearly", 6, 5000),
                    ("Yearly", 12, 9000),
                ],
            )

        con.commit()




def add_member():
    print("\n=== Add a New Member ===")

    name = input("Full name: ").strip()
    if not name:
        print("A name is needed to add a member.")
        return

    gender = input("Gender (optional): ").strip() or None
    phone = ask_optional(
        "Phone, 10 digits (optional): ", valid_phone,
        "Please enter exactly 10 digits, or leave it blank.",
    ) or None
    email = ask_optional(
        "Email (optional): ", valid_email,
        "That email doesn't look right. Try again, or leave it blank.",
    ) or None

    try:
        with closing(connect()) as con:
            con.execute(
                """
                INSERT INTO Members (name, gender, phone, email, join_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, gender, phone, email, date.today().isoformat()),
            )
            con.commit()
        print(f"Welcome aboard, {name}! Member added successfully.")

    except sqlite3.IntegrityError:
        print("Sorry, someone already has that phone number or email.")


def view_members():
    with closing(connect()) as con:
        rows = con.execute("SELECT * FROM Members").fetchall()

    print_table(
        "Members",
        ["ID", "Name", "Gender", "Phone", "Email", "Joined"],
        rows,
    )


def update_member():
    print("\n=== Update a Member ===")
    view_members()
    member_id = ask_int("\nMember ID to update: ")

    with closing(connect()) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT name, gender, phone, email FROM Members WHERE member_id = ?",
            (member_id,),
        )
        member = cur.fetchone()

        if not member:
            print("Sorry, no member with that ID.")
            return

        print("Press Enter to keep the current value.")
        name = input(f"Name [{member[0]}]: ").strip() or member[0]
        gender = input(f"Gender [{member[1] or ''}]: ").strip() or member[1]
        phone = ask_optional(
            f"Phone [{member[2] or ''}]: ", valid_phone,
            "Please enter exactly 10 digits, or press Enter to keep it.",
        ) or member[2]
        email = ask_optional(
            f"Email [{member[3] or ''}]: ", valid_email,
            "That email doesn't look right. Try again, or press Enter to keep it.",
        ) or member[3]

        try:
            cur.execute(
                """
                UPDATE Members SET name = ?, gender = ?, phone = ?, email = ?
                WHERE member_id = ?
                """,
                (name, gender, phone, email, member_id),
            )
            con.commit()
            print("Done! Member details updated.")

        except sqlite3.IntegrityError:
            print("Sorry, someone already has that phone number or email.")


def delete_member():
    print("\n=== Delete a Member ===")
    view_members()
    member_id = ask_int("\nMember ID to delete: ")

    with closing(connect()) as con:
        row = con.execute(
            "SELECT name FROM Members WHERE member_id = ?", (member_id,)
        ).fetchone()

        if not row:
            print("Sorry, no member with that ID.")
            return

        if not confirm(f"Really delete {row[0]}?"):
            print("No problem, nothing was deleted.")
            return

        try:
            con.execute("DELETE FROM Members WHERE member_id = ?", (member_id,))
            con.commit()
            print(f"{row[0]} has been deleted.")

        except sqlite3.IntegrityError:
            print(f"{row[0]} can't be deleted because they have membership, "
                  "payment or attendance records.")





def view_plans():
    with closing(connect()) as con:
        rows = con.execute("SELECT * FROM Membership_Plans").fetchall()

    print_table(
        "Membership Plans",
        ["ID", "Plan", "Months", "Price (Rs.)"],
        rows,
    )


def add_plan():
    print("\n=== Add a Membership Plan ===")

    name = input("Plan name: ").strip()
    if not name:
        print("A plan needs a name.")
        return

    duration = ask_int("How many months does it last? ")
    price = ask_float("Price (Rs.): ")

    if duration <= 0:
        print("The duration must be at least 1 month.")
        return
    if price < 0:
        print("The price can't be negative.")
        return

    try:
        with closing(connect()) as con:
            con.execute(
                """
                INSERT INTO Membership_Plans (plan_name, duration_months, price)
                VALUES (?, ?, ?)
                """,
                (name, duration, price),
            )
            con.commit()
        print(f"The '{name}' plan has been added.")

    except sqlite3.IntegrityError:
        print("A plan with that name already exists.")





def register_membership():
    print("\n=== Register a Membership ===")

    view_members()
    member_id = ask_int("\nMember ID: ")

    view_plans()
    plan_id = ask_int("\nPlan ID: ")

    update_expired()

    with closing(connect()) as con:
        cur = con.cursor()

        member = cur.execute(
            "SELECT name FROM Members WHERE member_id = ?", (member_id,)
        ).fetchone()
        if not member:
            print("Sorry, no member with that ID.")
            return

        plan = cur.execute(
            """
            SELECT plan_name, duration_months, price
            FROM Membership_Plans WHERE plan_id = ?
            """,
            (plan_id,),
        ).fetchone()
        if not plan:
            print("Sorry, no plan with that ID.")
            return

        already_active = cur.execute(
            "SELECT 1 FROM Memberships WHERE member_id = ? AND status = 'Active'",
            (member_id,),
        ).fetchone()
        if already_active:
            print(f"{member[0]} already has an active membership.")
            return

        plan_name, months, price = plan
        print(f"\n{member[0]} - {plan_name} plan, {money(price)}")

        method = choose_payment_method()
        if method is None:
            print("That payment option isn't valid, so nothing was saved.")
            return

        start = date.today()
        end = add_months(start, months)

        try:
            cur.execute(
                """
                INSERT INTO Memberships
                    (member_id, plan_id, start_date, end_date, status)
                VALUES (?, ?, ?, ?, 'Active')
                """,
                (member_id, plan_id, start.isoformat(), end.isoformat()),
            )
            membership_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO Payments
                    (membership_id, amount, payment_date, payment_method)
                VALUES (?, ?, ?, ?)
                """,
                (membership_id, price, start.isoformat(), method),
            )
            con.commit()

        except sqlite3.Error as error:
            con.rollback()
            print("Something went wrong, so nothing was saved:", error)
            return

    print("\nAll set! Membership registered.")
    print(f"  Membership ID : {membership_id}")
    print(f"  Valid from    : {start.isoformat()}")
    print(f"  Valid until   : {end.isoformat()}")
    print(f"  Paid          : {money(price)} by {method}")


def view_memberships():
    update_expired()

    with closing(connect()) as con:
        rows = con.execute(
            """
            SELECT ms.membership_id, m.name, p.plan_name,
                   ms.start_date, ms.end_date, ms.status
            FROM Memberships ms
            JOIN Members m ON ms.member_id = m.member_id
            JOIN Membership_Plans p ON ms.plan_id = p.plan_id
            """
        ).fetchall()

    print_table(
        "Memberships",
        ["ID", "Member", "Plan", "Start", "End", "Status"],
        rows,
    )


def cancel_membership():
    print("\n=== Cancel a Membership ===")
    view_memberships()
    membership_id = ask_int("\nMembership ID to cancel: ")

    with closing(connect()) as con:
        row = con.execute(
            """
            SELECT m.name FROM Memberships ms
            JOIN Members m ON ms.member_id = m.member_id
            WHERE ms.membership_id = ? AND ms.status = 'Active'
            """,
            (membership_id,),
        ).fetchone()

        if not row:
            print("There's no active membership with that ID.")
            return

        if not confirm(f"Cancel {row[0]}'s membership?"):
            print("No problem, the membership was left as it is.")
            return

        con.execute(
            "UPDATE Memberships SET status = 'Cancelled' WHERE membership_id = ?",
            (membership_id,),
        )
        con.commit()
        print("The membership has been cancelled.")


def record_payment():
    print("\n=== Record a Payment ===")
    view_memberships()

    membership_id = ask_int("\nMembership ID: ")
    amount = ask_float("Amount (Rs.): ")

    if amount <= 0:
        print("The amount must be more than zero.")
        return

    method = choose_payment_method()
    if method is None:
        print("That payment option isn't valid, so nothing was saved.")
        return

    with closing(connect()) as con:
        exists = con.execute(
            "SELECT 1 FROM Memberships WHERE membership_id = ?", (membership_id,)
        ).fetchone()
        if not exists:
            print("Sorry, no membership with that ID.")
            return

        con.execute(
            """
            INSERT INTO Payments
                (membership_id, amount, payment_date, payment_method)
            VALUES (?, ?, ?, ?)
            """,
            (membership_id, amount, date.today().isoformat(), method),
        )
        con.commit()

    print(f"Payment of {money(amount)} recorded. Thank you!")


def view_payments():
    with closing(connect()) as con:
        rows = con.execute(
            """
            SELECT pay.payment_id, m.name, pay.amount,
                   pay.payment_date, pay.payment_method
            FROM Payments pay
            JOIN Memberships ms ON pay.membership_id = ms.membership_id
            JOIN Members m ON ms.member_id = m.member_id
            """
        ).fetchall()

    print_table(
        "Payment History",
        ["ID", "Member", "Amount (Rs.)", "Date", "Method"],
        rows,
    )





def check_in():
    print("\n=== Check-in ===")
    member_id = ask_int("Member ID: ")

    with closing(connect()) as con:
        cur = con.cursor()

        member = cur.execute(
            "SELECT name FROM Members WHERE member_id = ?", (member_id,)
        ).fetchone()
        if not member:
            print("Sorry, no member with that ID.")
            return

        today = date.today().isoformat()

        valid = cur.execute(
            """
            SELECT 1 FROM Memberships
            WHERE member_id = ? AND status = 'Active'
              AND start_date <= ? AND end_date >= ?
            LIMIT 1
            """,
            (member_id, today, today),
        ).fetchone()
        if not valid:
            print(f"{member[0]} doesn't have a valid membership right now, "
                  "so check-in isn't allowed.")
            return

        already_in = cur.execute(
            "SELECT 1 FROM Attendance WHERE member_id = ? AND check_out IS NULL",
            (member_id,),
        ).fetchone()
        if already_in:
            print(f"{member[0]} is already checked in.")
            return

        cur.execute(
            "INSERT INTO Attendance (member_id, check_in) VALUES (?, ?)",
            (member_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        con.commit()

    print(f"Welcome, {member[0]}! You're checked in. Have a great workout!")


def check_out():
    print("\n=== Check-out ===")
    member_id = ask_int("Member ID: ")

    with closing(connect()) as con:
        cur = con.cursor()

        record = cur.execute(
            """
            SELECT a.attendance_id, a.check_in, m.name
            FROM Attendance a
            JOIN Members m ON a.member_id = m.member_id
            WHERE a.member_id = ? AND a.check_out IS NULL
            ORDER BY a.attendance_id DESC
            LIMIT 1
            """,
            (member_id,),
        ).fetchone()

        if not record:
            print("That member isn't checked in right now.")
            return

        attendance_id, check_in_text, name = record
        now = datetime.now()

        cur.execute(
            "UPDATE Attendance SET check_out = ? WHERE attendance_id = ?",
            (now.strftime("%Y-%m-%d %H:%M:%S"), attendance_id),
        )
        con.commit()

    started = datetime.strptime(check_in_text, "%Y-%m-%d %H:%M:%S")
    minutes = max(0, int((now - started).total_seconds() // 60))
    print(f"Thanks, {name}! You worked out for {minutes // 60}h {minutes % 60}m. "
          "See you next time!")


def view_attendance():
    with closing(connect()) as con:
        rows = con.execute(
            """
            SELECT a.attendance_id, m.name, a.check_in, a.check_out
            FROM Attendance a
            JOIN Members m ON a.member_id = m.member_id
            ORDER BY a.attendance_id DESC
            """
        ).fetchall()

    print_table(
        "Attendance",
        ["ID", "Member", "Check-in", "Check-out"],
        rows,
    )





def reports():
    update_expired()
    today = date.today().isoformat()

    with closing(connect()) as con:
        cur = con.cursor()

        total_members = cur.execute("SELECT COUNT(*) FROM Members").fetchone()[0]

        active = cur.execute(
            """
            SELECT COUNT(*) FROM Memberships
            WHERE status = 'Active' AND start_date <= ? AND end_date >= ?
            """,
            (today, today),
        ).fetchone()[0]

        expired = cur.execute(
            "SELECT COUNT(*) FROM Memberships WHERE status = 'Expired'"
        ).fetchone()[0]

        cancelled = cur.execute(
            "SELECT COUNT(*) FROM Memberships WHERE status = 'Cancelled'"
        ).fetchone()[0]

        revenue = cur.execute("SELECT SUM(amount) FROM Payments").fetchone()[0] or 0

        
        visits_today = cur.execute(
            "SELECT COUNT(*) FROM Attendance WHERE DATE(check_in) = ?", (today,)
        ).fetchone()[0]

    print("\n========== Gym Report ==========")
    print(f"Total members         : {total_members}")
    print(f"Active memberships    : {active}")
    print(f"Expired memberships   : {expired}")
    print(f"Cancelled memberships : {cancelled}")
    print(f"Total revenue         : {money(revenue)}")
    print(f"Visits today          : {visits_today}")





MENU = """
========================================
     GYM MEMBERSHIP MANAGEMENT SYSTEM
========================================

  MEMBERS
   1. Add member
   2. View members
   3. Update member
   4. Delete member

  PLANS
   5. View membership plans
   6. Add membership plan

  MEMBERSHIPS & PAYMENTS
   7. Register membership
   8. View memberships
   9. Cancel membership
  10. Record payment
  11. View payment history

  ATTENDANCE
  12. Check-in
  13. Check-out
  14. View attendance

  15. Reports
   0. Exit

========================================
"""


def main():
    create_tables()
    print("Hello! Welcome to the Gym Membership Management System.")

    actions = {
        "1": add_member,
        "2": view_members,
        "3": update_member,
        "4": delete_member,
        "5": view_plans,
        "6": add_plan,
        "7": register_membership,
        "8": view_memberships,
        "9": cancel_membership,
        "10": record_payment,
        "11": view_payments,
        "12": check_in,
        "13": check_out,
        "14": view_attendance,
        "15": reports,
    }

    while True:
        print(MENU)
        choice = input("What would you like to do? Enter a number: ").strip()

        if choice == "0":
            print("Thank you, and see you again soon!")
            break

        action = actions.get(choice)
        if action:
            action()
        else:
            print("Hmm, that's not on the menu. Please pick a number from the list.")


if __name__ == "__main__":
    main()