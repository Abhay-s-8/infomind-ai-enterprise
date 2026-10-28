"""Hand-written SYNTHETIC demonstration corpus with a labeled query set. No real or sensitive data.
Relevance labels for retrieval evaluation were assigned by the author: each query is built from a fact that appears in
exactly one document (`relevant`), which makes the labels unambiguous but also makes the task easy."""

DOCS: dict[str, str] = {
    "api_gateway_guide.txt": (
        "API Gateway Configuration Guide. The gateway exposes a REST endpoint on port 8443 and validates every request "
        "against a JSON schema. Rate limiting defaults to 120 requests per minute per client. Timeout settings can be "
        "changed in the gateway.yaml configuration file. Error code GW-502 indicates the upstream service did not respond."),
    "backup_runbook.txt": (
        "Database Backup Runbook. Full backups of the inventory database run every night at 02:30 and are retained for "
        "35 days. Restoring a backup requires the restore command and a verified checksum. Version compatibility between "
        "the backup tool and the server must be checked before installation."),
    "soil_moisture_study.txt": (
        "Research Report: Soil Moisture and Crop Yield. This study compares irrigation schedules across three field "
        "plots over 18 months. Results indicate a significant correlation between weekly irrigation and yield, with a "
        "12 percent improvement in the treated plots. Limitations include a small sample and a single growing region."),
    "bridge_inspection_survey.txt": (
        "Survey Findings: Bridge Inspections. The survey evaluated 46 footbridges and found corrosion in 9 of them. "
        "The methodology combined visual inspection with ultrasonic thickness measurement. Recommendations include "
        "repainting within two years and a follow-up review in 2026."),
    "office_move_memo.txt": (
        "Administration Memo: Office Relocation. The facilities team will move the records clerk and front desk to the "
        "second floor on 2025-09-12. Staff should return visitor badges and update room bookings. The department "
        "secretary will distribute the new meeting schedule and floor plan."),
    "leave_request_process.txt": (
        "Administration Note: Leave Requests. Human resources approves leave requests submitted through the shared "
        "filing system. The scheduling coordinator confirms coverage and archives the signed form. Onboarding "
        "paperwork for new employees is filed by the office manager."),
    "data_retention_policy.txt": (
        "Data Retention Policy. This policy mandates that employee records be retained for seven years and then "
        "securely destroyed. All employees must follow the approval and review process before exporting any records. "
        "Violations lead to disciplinary measures as defined in the code of conduct."),
    "acceptable_use_policy.txt": (
        "Acceptable Use Policy. The compliance office prohibits installing unapproved software on company laptops. "
        "Each department must complete the conflict of interest disclosure every January. Mandatory reporting "
        "obligations apply to suspected security incidents."),
    "vehicle_purchase_order.txt": (
        "Purchase Order PO-7781. The purchasing department issues this order to Northwind Supplies for six service "
        "vehicles at a unit price of $24,500. Payment terms are net 30 days. Approval was granted by the procurement "
        "officer on 2025-03-14 and the total of $147,000 is allocated to the fleet cost centre."),
    "q3_budget_forecast.txt": (
        "Quarterly Forecast and Budget. The finance team forecasts third quarter expenditure of $1.2 million with "
        "supplier invoices reconciled monthly. The budget office will audit the general ledger balance in October. "
        "The accounts payable clerk pays vendors within thirty days of invoice receipt."),
    "python_basics_course.txt": (
        "Course Syllabus: Python Basics. This course introduces programming fundamentals for beginners across eight "
        "weekly lessons. Learning objectives include variables, loops and functions. Assessment consists of quiz "
        "questions, two homework assignments and an end-of-course examination."),
    "first_aid_workshop.txt": (
        "Workshop: First Aid Training. The instructor teaches participants bandaging, recovery position and CPR "
        "during a practice lab on 2025-11-05. Each learner receives a certification after passing the skills "
        "assessment. Lesson slides and exercises are provided in advance."),
    "thank_you_note.txt": (
        "Hello Maria, thank you for your message and for the kind invitation to the upcoming visit. I am happy to "
        "confirm that we look forward to seeing you next week. Best wishes and kind regards from the team."),
    "schedule_change_email.txt": (
        "Hi team, I am writing regarding the change of plans for Friday. I regret to inform you that the lunch has "
        "moved to Monday. A brief reminder will follow. Thank you for your understanding."),
}

# (query, set of relevant filenames)
RETRIEVAL_QUERIES: list[tuple[str, set[str]]] = [
    ("What port does the gateway REST endpoint listen on?", {"api_gateway_guide.txt"}),
    ("How long are nightly database backups retained?", {"backup_runbook.txt"}),
    ("irrigation schedule effect on crop yield", {"soil_moisture_study.txt"}),
    ("footbridge corrosion inspection findings", {"bridge_inspection_survey.txt"}),
    ("when does the front desk move to the second floor", {"office_move_memo.txt"}),
    ("how are leave requests approved", {"leave_request_process.txt"}),
    ("how many years are employee records retained", {"data_retention_policy.txt"}),
    ("installing unapproved software on laptops", {"acceptable_use_policy.txt"}),
    ("purchase order for service vehicles from Northwind", {"vehicle_purchase_order.txt"}),
    ("third quarter expenditure forecast", {"q3_budget_forecast.txt"}),
    ("python programming course for beginners", {"python_basics_course.txt"}),
    ("first aid CPR certification workshop", {"first_aid_workshop.txt"}),
    ("invitation to the visit next week", {"thank_you_note.txt"}),
    ("lunch moved to Monday", {"schedule_change_email.txt"}),
]

# (question, expected answerable?, substring expected in a cited excerpt)
RAG_QUESTIONS: list[tuple[str, bool, str | None]] = [
    ("How long are nightly database backups retained?", True, "35 days"),
    ("What is the unit price of the service vehicles in PO-7781?", True, "24,500"),
    ("How many footbridges showed corrosion?", True, "9 of them"),
    ("How many years must employee records be retained?", True, "seven years"),
    ("What is the capital of Australia?", False, None),
    ("What is the CEO's home address?", False, None),
    ("What is the warp core temperature setting?", False, None),
]
