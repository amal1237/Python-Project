

import getpass
import hashlib
import os
import sqlite3
from contextlib import closing
from datetime import date, timedelta

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gym.db")
current_user = None


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=()):
    """Run a SELECT and return all rows."""
    with closing(connect()) as conn:
        return conn.execute(sql, params).fetchall()


def change(sql, params=()):
    """Run INSERT / UPDATE / DELETE and save it."""
    with closing(connect()) as conn:
        with conn:
            return conn.execute(sql, params).lastrowid


def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()


def setup_database():
    with closing(connect()) as conn:
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    username  TEXT NOT NULL UNIQUE,
                    password  TEXT NOT NULL,
                    role      TEXT NOT NULL CHECK (role IN ('admin','staff','member')),
                    full_name TEXT NOT NULL,
                    phone     TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_name TEXT NOT NULL UNIQUE,
                    days      INTEGER NOT NULL CHECK (days > 0),
                    price     REAL NOT NULL CHECK (price >= 0)
                );
                CREATE TABLE IF NOT EXISTS memberships (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    plan_id    INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date   TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (plan_id) REFERENCES plans (plan_id) ON DELETE RESTRICT
                );
            """)
    if not query("SELECT 1 FROM users"):
        users = [("admin", "admin123", "admin", "Gym Admin", "9000000001"),
                 ("staff1", "staff123", "staff", "Sam Staff", "9000000002"),
                 ("john", "john123", "member", "John Carter", "9876543210")]
        for username, pw, role, name, phone in users:
            change("INSERT INTO users (username, password, role, full_name, phone) "
                   "VALUES (?, ?, ?, ?, ?)", (username, hash_pw(pw), role, name, phone))
        for plan in [("Monthly", 30, 30.0), ("Quarterly", 90, 80.0), ("Yearly", 365, 280.0)]:
            change("INSERT INTO plans (plan_name, days, price) VALUES (?, ?, ?)", plan)
        start = date.today()
        change("INSERT INTO memberships (user_id, plan_id, start_date, end_date) "
               "VALUES (3, 1, ?, ?)", (start.isoformat(), (start + timedelta(days=30)).isoformat()))


def ask(prompt, default=None):
    """Ask until the user types something (Enter keeps the default, if any)."""
    while True:
        text = input(prompt).strip()
        if text:
            return text
        if default is not None:
            return str(default)
        print("Input cannot be empty.")


def ask_number(prompt, kind=int, minimum=0, default=None):
    while True:
        try:
            value = kind(ask(prompt, default))
            if value >= minimum:
                return value
            print(f"Enter a value of at least {minimum}.")
        except ValueError:
            print("Enter a valid number.")


def ask_phone(prompt, default=None):
    while True:
        phone = ask(prompt, default)
        if phone.isascii() and phone.isdigit() and 7 <= len(phone) <= 15:
            return phone
        print("Phone must be 7-15 digits.")


def ask_yes(prompt):
    return input(prompt + " (y/n): ").strip().lower() == "y"


def show(headers, rows):
    if not rows:
        print("No records found.")
        return
    print(" | ".join(headers))
    print("-" * 60)
    for row in rows:
        print(" | ".join(str(item) for item in row))


def register(role="member"):
    username = ask("Username: ").lower()
    if query("SELECT 1 FROM users WHERE username = ?", (username,)):
        print("That username is already taken.")
        return
    while True:
        password = getpass.getpass("Password (min 6 characters): ")
        if len(password) >= 6:
            break
        print("Password is too short.")
    name = ask("Full name: ")
    phone = ask_phone("Phone: ")
    change("INSERT INTO users (username, password, role, full_name, phone) "
           "VALUES (?, ?, ?, ?, ?)", (username, hash_pw(password), role, name, phone))
    print(f"{role.capitalize()} account created.")


def add_member():
    register("member")


def add_staff():
    register("staff")


def login():
    global current_user
    for attempt in range(3):
        username = ask("Username: ").lower()
        password = getpass.getpass("Password: ")
        rows = query("SELECT user_id, full_name, role FROM users "
                     "WHERE username = ? AND password = ?", (username, hash_pw(password)))
        if rows:
            current_user = {"id": rows[0][0],
                            "name": rows[0][1], "role": rows[0][2]}
            print(f"Welcome, {current_user['name']}!")
            return True
        print(f"Wrong username or password. Attempts left: {2 - attempt}")
    return False


def logout():
    global current_user
    current_user = None
    print("Logged out.")


def list_users():
    sql = "SELECT user_id, username, role, full_name, phone FROM users"
    if current_user["role"] == "staff":
        sql += " WHERE role = 'member'"  # staff only see members
    show(["ID", "Username", "Role", "Name", "Phone"], query(sql))


def find_user():
    """Ask for a user ID and return (id, name, phone, role) or None."""
    rows = query("SELECT user_id, full_name, phone, role FROM users WHERE user_id = ?",
                 (ask_number("User ID: ", minimum=1),))
    if not rows or (current_user["role"] == "staff" and rows[0][3] != "member"):
        print("No such user.")
        return None
    return rows[0]


def update_user():
    user = find_user()
    if user:
        print("Press Enter to keep the current value.")
        name = ask(f"Name [{user[1]}]: ", user[1])
        phone = ask_phone(f"Phone [{user[2]}]: ", user[2])
        change("UPDATE users SET full_name = ?, phone = ? WHERE user_id = ?",
               (name, phone, user[0]))
        print("Updated.")


def delete_user():
    user = find_user()
    if not user:
        return
    if user[0] == current_user["id"]:
        print("You cannot delete your own account.")
    elif ask_yes(f"Delete {user[1]} and all their memberships?"):
        change("DELETE FROM users WHERE user_id = ?", (user[0],))
        print("Deleted.")


def list_plans():
    show(["ID", "Plan", "Days", "Price"], query("SELECT * FROM plans"))


def add_plan():
    name = ask("Plan name: ")
    days = ask_number("Days: ", minimum=1)
    price = ask_number("Price: ", float)
    change("INSERT INTO plans (plan_name, days, price) VALUES (?, ?, ?)",
           (name, days, price))
    print("Plan added.")


def find_plan():
    rows = query("SELECT * FROM plans WHERE plan_id = ?",
                 (ask_number("Plan ID: ", minimum=1),))
    if not rows:
        print("No such plan.")
    return rows[0] if rows else None


def update_plan():
    plan = find_plan()
    if plan:
        print("Press Enter to keep the current value.")
        name = ask(f"Name [{plan[1]}]: ", plan[1])
        days = ask_number(f"Days [{plan[2]}]: ", minimum=1, default=plan[2])
        price = ask_number(f"Price [{plan[3]}]: ", float, default=plan[3])
        change("UPDATE plans SET plan_name = ?, days = ?, price = ? WHERE plan_id = ?",
               (name, days, price, plan[0]))
        print("Plan updated.")


def delete_plan():
    plan = find_plan()
    if plan and ask_yes(f"Delete plan {plan[1]}?"):
        change("DELETE FROM plans WHERE plan_id = ?",
               (plan[0],))  # fails if plan is in use
        print("Plan deleted.")


def list_memberships(only_mine=False):
    sql = ("SELECT m.membership_id, u.full_name, p.plan_name, m.start_date, m.end_date, "
           "CASE WHEN m.end_date >= ? THEN 'Active' ELSE 'Expired' END "
           "FROM memberships m JOIN users u ON u.user_id = m.user_id "
           "JOIN plans p ON p.plan_id = m.plan_id")
    params = [date.today().isoformat()]
    if only_mine:
        sql += " WHERE m.user_id = ?"
        params.append(current_user["id"])
    show(["ID", "Member", "Plan", "Start", "End", "Status"], query(sql, params))


def my_memberships():
    list_memberships(only_mine=True)


def assign_membership():
    if current_user["role"] == "member":
        user_id = current_user["id"]
    else:
        user = find_user()
        if not user:
            return
        if user[3] != "member":
            print("Only members can have memberships.")
            return
        user_id = user[0]
    list_plans()
    plan = find_plan()
    if not plan:
        return
    start = date.today()
    last_end = query(
        "SELECT MAX(end_date) FROM memberships WHERE user_id = ?", (user_id,))[0][0]
    if last_end and last_end >= start.isoformat():  # renewal starts after current plan
        start = date.fromisoformat(last_end) + timedelta(days=1)
    end = start + timedelta(days=plan[2])
    change("INSERT INTO memberships (user_id, plan_id, start_date, end_date) "
           "VALUES (?, ?, ?, ?)", (user_id, plan[0], start.isoformat(), end.isoformat()))
    print(f"Membership created: {start} to {end}. Price: {plan[3]:.2f}")


def delete_membership():
    membership_id = ask_number("Membership ID: ", minimum=1)
    if not query("SELECT 1 FROM memberships WHERE membership_id = ?", (membership_id,)):
        print("No such membership.")
    elif ask_yes("Delete this membership?"):
        change("DELETE FROM memberships WHERE membership_id = ?", (membership_id,))
        print("Deleted.")


def run_menu(title, options, exit_text="Back"):
    while True:
        print(f"\n=== {title} ===")
        for number, (label, _) in enumerate(options, 1):
            print(f"{number}. {label}")
        print(f"0. {exit_text}")
        try:
            choice = int(input("Choose an option: ").strip())
        except ValueError:
            print("Invalid choice. Type a number from the menu.")
            continue
        if choice == 0:
            return
        if not 1 <= choice <= len(options):
            print("Invalid choice. Pick a number from the menu.")
            continue
        try:
            options[choice - 1][1]()
        except sqlite3.IntegrityError:
            print("Error: duplicate value, or the record is linked to other records.")
        except sqlite3.Error as error:
            print(f"Database error: {error}")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except EOFError:
            raise
        except Exception as error:
            print(f"Unexpected error: {error}")


def role_menu():
    role = current_user["role"]
    if role == "admin":
        options = [("Add staff account", add_staff), ("Add member", add_member),
                   ("View users", list_users), ("Update user", update_user),
                   ("Delete user", delete_user), ("View plans", list_plans),
                   ("Add plan", add_plan), ("Update plan", update_plan),
                   ("Delete plan", delete_plan), ("Assign membership", assign_membership),
                   ("View memberships", list_memberships),
                   ("Delete membership", delete_membership)]
    elif role == "staff":
        options = [("Add member", add_member), ("View members", list_users),
                   ("Update member", update_user), ("View plans", list_plans),
                   ("Assign membership", assign_membership),
                   ("View memberships", list_memberships)]
    else:
        options = [("View plans", list_plans), ("Buy / renew membership", assign_membership),
                   ("My memberships", my_memberships)]
    run_menu(f"{role.upper()} MENU", options, "Logout")
    logout()


def main():
    try:
        setup_database()
    except (sqlite3.Error, OSError) as error:
        print(f"Could not set up the database: {error}")
        return
    try:
        while True:
            print(
                "\n=== GYM MEMBERSHIP SYSTEM ===\n1. Login\n2. Register as member\n0. Exit")
            choice = input("Choose an option: ").strip()
            if choice == "1":
                if login():
                    role_menu()
            elif choice == "2":
                try:
                    register()
                except sqlite3.Error as error:
                    print(f"Database error: {error}")
            elif choice == "0":
                print("Goodbye!")
                return
            else:
                print("Invalid choice. Type 1, 2 or 0.")
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
