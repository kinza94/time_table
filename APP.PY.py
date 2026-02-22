import streamlit as st
import pandas as pd
import sqlite3
import json

conn = sqlite3.connect("school.db", check_same_thread=False)
c = conn.cursor()

# Create table
c.execute("""
CREATE TABLE IF NOT EXISTS app_data (
    id INTEGER PRIMARY KEY,
    data TEXT
)
""")

conn.commit()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None

if not st.session_state.logged_in:

    st.title("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if username == "admin" and password == "1234567":
            st.session_state.logged_in = True
            st.session_state.role = "admin"
            st.success("Logged in as Admin")
            st.rerun()

        elif username == "teacher" and password == "1234":
            st.session_state.logged_in = True
            st.session_state.role = "teacher"
            st.success("Logged in as Teacher")
            st.rerun()

        else:
            st.error("Invalid credentials")

    st.stop()

if st.session_state.role == "admin":
    if st.button("Generate Timetable", key="admin_generate"):
        pass


# ==================================================
# ---------------- APP SETUP -----------------------
# ==================================================
st.set_page_config(page_title="School Scheduler Pro", layout="wide")

st.markdown("""
    <style>
        .main {
            background-color: #f4f7fb;
        }
        h1 {
            color: #1f4e79;
        }
        .stButton>button {
            background-color: #4a90e2;
            color: white;
            border-radius: 8px;
            height: 3em;
            width: 100%;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📚 School Timetable Scheduler Pro")

# ==================================================
# ---------------- GLOBAL CONSTANTS ----------------
# ==================================================
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

ALL_PERIODS = ["P1","P2","P3","P4","P5","Lunch","P6","P7","P8"]

def get_periods(day):
    if day == "Friday":
        return ["P1","P2","P3","P4","Lunch","P5","P6"]
    return ALL_PERIODS

# ==================================================
# ---------------- SESSION STATE -------------------
# ==================================================
# ==================================================
# ---------------- SESSION STATE -------------------
# ==================================================

if "teachers" not in st.session_state:
    st.session_state.teachers = {}

if "sections" not in st.session_state:
    st.session_state.sections = {}

if "class_teachers" not in st.session_state:
    st.session_state.class_teachers = {}

if "subject_config" not in st.session_state:
    st.session_state.subject_config = {}

if "teacher_assignment" not in st.session_state:
    st.session_state.teacher_assignment = {}

if "timetable" not in st.session_state:
    st.session_state.timetable = {}

def save_all_data():

    data = {
        "teachers": st.session_state.get("teachers", {}),
        "sections": st.session_state.get("sections", {}),
        "class_teachers": st.session_state.get("class_teachers", {}),
        "subject_config": st.session_state.get("subject_config", {}),
        "teacher_assignment": st.session_state.get("teacher_assignment", {}),
        "timetable": st.session_state.get("timetable", {}),
    }

    c.execute("DELETE FROM app_data")
    c.execute("INSERT INTO app_data (data) VALUES (?)",
              (json.dumps(data),))
    conn.commit()


def load_all_data():

    c.execute("SELECT data FROM app_data LIMIT 1")
    row = c.fetchone()

    if row:
        data = json.loads(row[0])

        st.session_state.teachers = data.get("teachers", {})
        st.session_state.sections = data.get("sections", {})
        st.session_state.class_teachers = data.get("class_teachers", {})
        st.session_state.subject_config = data.get("subject_config", {})
        st.session_state.teacher_assignment = data.get("teacher_assignment", {})
        st.session_state.timetable = data.get("timetable", {})

def validate_subject_weekly(section):
    issues = []

    if section not in st.session_state.subject_config:
        return issues

    required_counts = st.session_state.subject_config[section]
    actual_counts = {}

    # Count actual subjects in timetable
    for day in DAYS:
        for period in get_periods(day):
            subject = st.session_state.timetable[section][day][period]["subject"]
            if subject:
                actual_counts[subject] = actual_counts.get(subject, 0) + 1

    # Compare with required
    for subject, required in required_counts.items():
        actual = actual_counts.get(subject, 0)
        if actual != required:
            issues.append(
                f"{subject} should be {required} periods but currently {actual}"
            )

    return issues
def validate_teacher_clashes():
    issues = []

    for day in DAYS:
        for period in get_periods(day):

            teacher_slots = {}

            for section in st.session_state.timetable:

                teacher = st.session_state.timetable[section][day][period]["teacher"]

                if teacher:

                    if teacher not in teacher_slots:
                        teacher_slots[teacher] = []

                    teacher_slots[teacher].append(section)

            # If same teacher in multiple sections
            for teacher, sections in teacher_slots.items():
                if len(sections) > 1:
                    issues.append(
                        f"Clash: {teacher} has {sections} at {day} {period}"
                    )

    return issues
def validate_class_teacher_presence():
    issues = []

    for section, class_teacher in st.session_state.class_teachers.items():

        found = False

        for day in DAYS:
            for period in get_periods(day):

                teacher = st.session_state.timetable[section][day][period]["teacher"]

                if teacher == class_teacher:
                    found = True
                    break

            if found:
                break

        if not found:
            issues.append(
                f"Class teacher {class_teacher} has no period in {section}"
            )

    return issues
load_all_data()
#==================================================
# AI DETECTION ENGINE
#============================================
def find_alternative_teacher(section, subject, day, period):

    alternatives = []

    for teacher, sec_data in st.session_state.teacher_assignment.items():

        if section in sec_data and subject in sec_data[section]:

            # Skip original teacher
            if teacher == st.session_state.timetable[section][day][period]["teacher"]:
                continue

            if not teacher_busy(teacher, day, period):
                alternatives.append(teacher)

    return alternatives
def find_swap_option(section, teacher, subject, day, period):

    swaps = []

    for d in DAYS:
        for p in get_periods(d):

            if (d == day and p == period):
                continue

            if st.session_state.timetable[section][d][p]["teacher"] == teacher:

                # Check if swapping avoids clash
                if not teacher_busy(teacher, day, period):

                    swaps.append((d, p))

    return swaps




# ==================================================
# ---------------- CREATE TIMETABLE ----------------
# ==================================================
import random

# --------------------------------------------
# CREATE EMPTY TIMETABLE
# --------------------------------------------
def create_empty_timetable():
    timetable = {}

    for section in st.session_state.sections:
        timetable[section] = {}
        for day in DAYS:
            timetable[section][day] = {}
            for period in get_periods(day):
                timetable[section][day][period] = {
                    "subject": "",
                    "teacher": ""
                }

    return timetable
# TEACHER BUSY CHECK
# ----------------------------
def teacher_busy(teacher, day, period):
    for sec in st.session_state.timetable:
        if st.session_state.timetable[sec][day][period]["teacher"] == teacher:
            return True
    return False

def assign_class_teacher_priority():

    for section, class_teacher in st.session_state.class_teachers.items():

        # Check if teacher teaches any subject in this section
        if class_teacher not in st.session_state.teacher_assignment:
            continue

        if section not in st.session_state.teacher_assignment[class_teacher]:
            continue

        subjects = st.session_state.teacher_assignment[class_teacher][section]

        for day in DAYS:

            if "P1" not in get_periods(day):
                continue

            if not subjects:
                continue

            # Pick first subject assigned to class teacher
            subject = subjects[0]

            # Check if subject still needs periods
            required = st.session_state.subject_config[section].get(subject, 0)

            if required <= 0:
                continue

            # Check slot free & teacher not busy
            if (
                st.session_state.timetable[section][day]["P1"]["subject"] == ""
                and not teacher_busy(class_teacher, day, "P1")
            ):

                st.session_state.timetable[section][day]["P1"]["subject"] = subject
                st.session_state.timetable[section][day]["P1"]["teacher"] = class_teacher

                # Reduce required count
                st.session_state.subject_config[section][subject] -= 1


# --------------------------------------------
# BASIC AUTO FILL ENGINE
# --------------------------------------------
def basic_auto_fill():

    import random

    for section in st.session_state.subject_config:

        subjects = st.session_state.subject_config[section]

        for subject, count in subjects.items():

            assigned_teacher = None

            # Find teacher
            for teacher, sec_data in st.session_state.teacher_assignment.items():
                if section in sec_data and subject in sec_data[section]:
                    assigned_teacher = teacher
                    break

            if not assigned_teacher:
                continue

            filled = 0
            subject_day_count = {day: 0 for day in DAYS}

            while filled < count:

                placed = False
                days_shuffled = DAYS.copy()
                random.shuffle(days_shuffled)

                for day in days_shuffled:

                    if subject_day_count[day] >= 2:
                        continue

                    periods = get_periods(day)
                    periods_shuffled = periods.copy()
                    random.shuffle(periods_shuffled)

                    for period in periods_shuffled:

                        if period == "Lunch":
                            continue

                        # ✅ Correct condition placement
                        if (
                            st.session_state.timetable[section][day][period]["subject"] == ""
                            and not teacher_busy(assigned_teacher, day, period)
                        ):

                            st.session_state.timetable[section][day][period]["subject"] = subject
                            st.session_state.timetable[section][day][period]["teacher"] = assigned_teacher

                            subject_day_count[day] += 1
                            filled += 1
                            placed = True
                            break

                    if placed:
                        break

                if not placed:
                    break

# SUGGESTION============================================
def get_free_teachers(day, period):

    free = []

    for teacher in st.session_state.teachers:
        if not teacher_busy(teacher, day, period):
            free.append(teacher)

    return free

def suggest_safe_slots(section, teacher):

    safe = []

    for day in DAYS:
        for period in get_periods(day):

            if period == "Lunch":
                continue

            if (
                st.session_state.timetable[section][day][period]["subject"] == ""
                and not teacher_busy(teacher, day, period)
            ):
                safe.append((day, period))

    return safe[:5]



# ==================================================
# ---------------- SIDEBAR -------------------------
# ==================================================
menu = st.sidebar.selectbox(
    "Navigation",
    ["Dashboard", "Configuration", "Generate", "Class View", "Teacher View", "Analytics"]
)

# ==================================================
# ---------------- DASHBOARD -----------------------
# ==================================================
if menu == "Dashboard":
    st.subheader("CREATE YOUR TIME TABLE👋")
    st.write("Use sidebar to configure and generate timetable.")


# ==================================================
# ---------------- CONFIGURATION -------------------
# ==================================================
if menu == "Configuration":

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Add Section")
        sec = st.text_input("Section Name (e.g., 6A)")
        if st.button("Add Section"):
            st.session_state.sections[sec] = {}
            st.success("Section Added")

        st.write("Sections:", list(st.session_state.sections.keys()))
        if st.session_state.sections:
            remove_sec = st.selectbox(
                "Remove Section",
                list(st.session_state.sections.keys()),
                key="remove_section_select"
            )

            if st.button("Delete Section"):
                st.session_state.sections.pop(remove_sec, None)
                st.session_state.subject_config.pop(remove_sec, None)
                st.session_state.class_teachers.pop(remove_sec, None)
                st.success("Section Removed")
                save_all_data()

    with col2:
        st.subheader("➕ Add Teacher")
        teacher = st.text_input("Teacher Name")
        if st.button("Add Teacher"):
            st.session_state.teachers[teacher] = {}
            st.success("Teacher Added")

        st.write("Teachers:", list(st.session_state.teachers.keys()))
        if st.session_state.teachers:
            remove_teacher = st.selectbox(
                "Remove Teacher",
                list(st.session_state.teachers.keys()),
                key="remove_teacher_select"
            )

            if st.button("Delete Teacher"):
                st.session_state.teachers.pop(remove_teacher, None)
                st.success("Teacher Removed")
                save_all_data()


    st.subheader("📌 Assign Class Teacher")

    if st.session_state.sections and st.session_state.teachers:
        selected_sec = st.selectbox(
            "Select Section",
            list(st.session_state.sections.keys()),
            key="class_teacher_section"
        )

        selected_teacher = st.selectbox("Select Teacher", list(st.session_state.teachers.keys()))

        if st.button("Assign"):
            st.session_state.class_teachers[selected_sec] = selected_teacher
            st.success("Class Teacher Assigned")

    st.write("Class Teachers:", st.session_state.class_teachers)
    if st.session_state.class_teachers:
        remove_class_teacher = st.selectbox(
            "Remove Class Teacher",
            list(st.session_state.class_teachers.keys()),
            key="remove_class_teacher_select"
        )

        if st.button("Delete Class Teacher"):
            st.session_state.class_teachers.pop(remove_class_teacher, None)
            st.success("Class Teacher Removed")
            save_all_data()


    st.subheader("📚 Configure Subjects for Section")

    if st.session_state.sections:

        selected_section = st.selectbox(
            "Select Section",
            list(st.session_state.sections.keys()),
            key="subject_config_section"
        )

        subject_name = st.text_input("Subject Name (e.g., Maths)")
        weekly_periods = st.number_input("Weekly Periods", min_value=1, max_value=10, step=1)

        if st.button("Add Subject"):
            if selected_section not in st.session_state.subject_config:
                st.session_state.subject_config[selected_section] = {}

            st.session_state.subject_config[selected_section][subject_name] = weekly_periods
            st.success("Subject Added Successfully")

        st.write("### Subjects for this Section:")
        st.write(st.session_state.subject_config.get(selected_section, {}))
        subjects_for_section = st.session_state.subject_config.get(selected_section, {})

        if subjects_for_section:
            remove_subject = st.selectbox(
                "Remove Subject",
                list(subjects_for_section.keys()),
                key="remove_subject_select"
            )

            if st.button("Delete Subject"):
                st.session_state.subject_config[selected_section].pop(remove_subject, None)
                st.success("Subject Removed")


st.subheader("👩‍🏫 Assign Teacher to Section & Subject")

if st.session_state.teachers and st.session_state.subject_config:

    assign_teacher = st.selectbox(
        "Select Teacher",
        list(st.session_state.teachers.keys()),
        key="assign_teacher_select"
    )

    assign_section = st.selectbox(
        "Select Section",
        list(st.session_state.subject_config.keys()),
        key="assign_section_select"
    )

    subjects_available = list(
        st.session_state.subject_config.get(assign_section, {}).keys()
    )

    if subjects_available:
        assign_subject = st.selectbox(
            "Select Subject",
            subjects_available,
            key="assign_subject_select"
        )

        if st.button("Assign Teacher"):

            if assign_teacher not in st.session_state.teacher_assignment:
                st.session_state.teacher_assignment[assign_teacher] = {}

            if assign_section not in st.session_state.teacher_assignment[assign_teacher]:
                st.session_state.teacher_assignment[assign_teacher][assign_section] = []

            if assign_subject not in st.session_state.teacher_assignment[assign_teacher][assign_section]:
                st.session_state.teacher_assignment[assign_teacher][assign_section].append(assign_subject)

            st.success("Teacher Assigned Successfully")


    st.write("### Current Teacher Assignments")
    st.write(st.session_state.teacher_assignment)
    st.subheader("❌ Remove Teacher Assignment")

    if st.session_state.teacher_assignment:

        remove_teacher = st.selectbox(
            "Select Teacher",
            list(st.session_state.teacher_assignment.keys()),
            key="remove_assign_teacher"
        )

        sections_for_teacher = list(
            st.session_state.teacher_assignment[remove_teacher].keys()
        )

        if sections_for_teacher:

            remove_section = st.selectbox(
                "Select Section",
                sections_for_teacher,
                key="remove_assign_section"
            )

            subjects_for_teacher = st.session_state.teacher_assignment[remove_teacher][remove_section]

            if subjects_for_teacher:

                remove_subject = st.selectbox(
                    "Select Subject",
                    subjects_for_teacher,
                    key="remove_assign_subject"
                )

                if st.button("Delete Assignment"):

                    st.session_state.teacher_assignment[remove_teacher][remove_section].remove(remove_subject)

                    # Clean empty structures
                    if not st.session_state.teacher_assignment[remove_teacher][remove_section]:
                        del st.session_state.teacher_assignment[remove_teacher][remove_section]

                    if not st.session_state.teacher_assignment[remove_teacher]:
                        del st.session_state.teacher_assignment[remove_teacher]

                    st.success("Assignment Removed Successfully")


# ==================================================
# ---------------- GENERATE ------------------------
# ==================================================
if menu == "Generate":

    if st.button("Generate Timetable", key="generate_main"):

        # Make deep copy of original subject config
        original_config = {
            sec: st.session_state.subject_config[sec].copy()
            for sec in st.session_state.subject_config
        }

        st.session_state.timetable = create_empty_timetable()

        assign_class_teacher_priority()
        basic_auto_fill()

        # Restore original subject config
        st.session_state.subject_config = original_config

        st.success("Timetable Generated with Class Teacher P1 Priority")
        save_all_data()
        # ===============================
        # RUN ALL VALIDATIONS
        # ===============================

        for sec in st.session_state.timetable:
            subject_issues = validate_subject_weekly(sec)
            for issue in subject_issues:
                st.error(issue)

        clash_issues = validate_teacher_clashes()
        for issue in clash_issues:
            st.error(issue)

        class_teacher_issues = validate_class_teacher_presence()
        for issue in class_teacher_issues:
            st.warning(issue)

        max_load_issues = validate_teacher_max_load()
        for issue in max_load_issues:
            st.error(issue)




# ==================================================
# ---------------- CLASS VIEW ----------------------
# ==================================================
if menu == "Class View":

    if not st.session_state.timetable:
        st.warning("Generate timetable first")
    else:
        sec = st.selectbox("Select Section", list(st.session_state.timetable.keys()))

        df_data = {}

        for day in DAYS:
            row = []
            for p in ALL_PERIODS:
                if p in get_periods(day):
                    subject = st.session_state.timetable.get(section, {}) \
                        .get(day, {}) \
                        .get(period, {}) \
                        .get("subject", "")
                    teacher = st.session_state.timetable[sec][day][p]["teacher"]
                    value = f"{subject} | {teacher}" if subject else ""
                    row.append(value)
                else:
                    row.append("")
            df_data[day] = row

        df = pd.DataFrame(df_data, index=ALL_PERIODS)

        edited_df = st.data_editor(df, use_container_width=True)

        # ✅ SAVE BUTTON MUST BE HERE
        if st.button("Save Manual Changes"):

            for day in DAYS:
                for period in ALL_PERIODS:
                    if period in get_periods(day):

                        cell = edited_df.loc[period, day]

                        if cell:
                            try:
                                subject, teacher = cell.split("|")
                                subject = subject.strip()
                                teacher = teacher.strip()

                                st.session_state.timetable[sec][day][period]["subject"] = subject
                                st.session_state.timetable[sec][day][period]["teacher"] = teacher
                            except:
                                pass
                        else:
                            st.session_state.timetable[sec][day][period]["subject"] = ""
                            st.session_state.timetable[sec][day][period]["teacher"] = ""

            save_all_data()
            st.success("Manual changes saved")

#===================================
#------- max 25 periods per week----
#===================================
def validate_teacher_max_load(max_periods=25):

    issues = []

    for teacher in st.session_state.teachers:

        count = 0

        for sec in st.session_state.timetable:
            for day in DAYS:
                for period in get_periods(day):
                    if st.session_state.timetable[sec][day][period]["teacher"] == teacher:
                        count += 1

        if count > max_periods:
            issues.append(f"{teacher} exceeds {max_periods} periods (currently {count})")

    return issues





# ==================================================
# ---------------- TEACHER VIEW --------------------
# ==================================================
if menu == "Teacher View":

    if not st.session_state.timetable:
        st.warning("Generate timetable first")
    else:

        teacher = st.selectbox(
            "Select Teacher",
            list(st.session_state.teachers.keys()),
            key="teacher_view_select"
        )

        # Create empty structure
        df_data = {}

        for day in DAYS:
            row = []
            for p in ALL_PERIODS:

                if p in get_periods(day):
                    found = False

                    for sec in st.session_state.timetable:
                        if (
                            st.session_state.timetable[sec][day][p]["teacher"]
                            == teacher
                        ):
                            subject = st.session_state.timetable[sec][day][p]["subject"]
                            row.append(f"{sec}\n{subject}")
                            found = True
                            break

                    if not found:
                        row.append("")
                else:
                    row.append("")

            df_data[day] = row

        df = pd.DataFrame(df_data, index=ALL_PERIODS)
        st.dataframe(df)

        # Total count
        total = 0
        for sec in st.session_state.timetable:
            for day in DAYS:
                for period in get_periods(day):
                    if (
                        st.session_state.timetable[sec][day][period]["teacher"]
                        == teacher
                    ):
                        total += 1

        st.write(f"### Total Weekly Periods: {total}")

# ==================================================
# ---------------- ANALYTICS -----------------------
# ==================================================
if menu == "Analytics":

    if not st.session_state.timetable:
        st.warning("Generate timetable first")
    else:
        workload = {}

        for teacher in st.session_state.teachers:
            count = 0
            for sec in st.session_state.timetable:
                for day in DAYS:
                    for period in get_periods(day):
                        if st.session_state.timetable[sec][day][period]["teacher"] == teacher:
                            count += 1
            workload[teacher] = count

        df = pd.DataFrame(workload.items(), columns=["Teacher", "Total Periods"])
        st.dataframe(df)
        st.bar_chart(df.set_index("Teacher"))
