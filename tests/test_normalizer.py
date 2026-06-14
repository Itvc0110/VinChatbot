from vinchatbot.app.ingest.normalizer import infer_category


def test_infer_category_groups_conduct_cluster():
    # The Student Code of Conduct family must all land in student_affairs/conduct so routing
    # and subcategory boosts treat them as one domain — including the disciplinary appendices
    # and the Vietnamese regulation whose titles omit the word "conduct".
    cases = [
        "https://policy.vinuni.edu.vn/all-policies/student-affairs-regulations-code-of-conduct/",
        "https://policy.vinuni.edu.vn/wp-content/uploads/2025/12/VU_CTSV02_Student-Code-of-Conduct.pdf",
        "https://policy.vinuni.edu.vn/wp-content/uploads/2025/12/Appendix-II-Disciplinary-Procedures_ENG.pdf",
        "https://policy.vinuni.edu.vn/wp-content/uploads/2025/12/Appendix-III.-Type-of-Violations.pdf",
        "https://policy.vinuni.edu.vn/wp-content/uploads/2025/12/Appendix-I-Student-behaviours_ENG.pdf",
        "https://policy.vinuni.edu.vn/wp-content/uploads/2025/12/VU_CTSV02_Quy-che-cong-tac-sinh-vien_VIE.pdf",
    ]
    for url in cases:
        assert infer_category(url, "") == ("student_affairs", "conduct"), url


def test_infer_category_keeps_existing_mappings():
    assert infer_category("https://vinuni.edu.vn/academic-calendar/", "") == ("academic", "calendar")
    assert infer_category("https://registrar.vinuni.edu.vn/academics/transfer-credit/", "") == ("academic", "registrar")
    assert infer_category("https://policy.vinuni.edu.vn/all-policies/financial-regulations-and-tariff/", "") == (
        "student_affairs",
        "financial",
    )
    # A plain policy page without conduct/discipline terms stays student_affairs/policy.
    assert infer_category("https://policy.vinuni.edu.vn/all-policies/research-integrity-policy/", "") == (
        "student_affairs",
        "policy",
    )
