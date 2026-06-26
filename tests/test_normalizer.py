from vinchatbot.app.ingest.normalizer import infer_category, infer_source_kind


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


def test_infer_category_expansion_content():
    assert infer_category("https://admissions.vinuni.edu.vn/undergraduate/faqs/general-admissions", "") == (
        "student_services",
        "admissions",
    )
    assert infer_category("https://scholarships.vinuni.edu.vn/vingroup-2025", "") == ("student_affairs", "financial")
    assert infer_category("https://cecs.vinuni.edu.vn/undergraduate/computer-science/", "") == ("academic", "program")


def test_infer_source_kind_expansion_keeps_student_relevant_drops_college_marketing():
    # Admissions / scholarships / college PROGRAM pages get high-value kinds (so --student-only keeps them)...
    assert infer_source_kind("https://admissions.vinuni.edu.vn/undergraduate/faqs/general-admissions") == "faq_page"
    assert infer_source_kind("https://admissions.vinuni.edu.vn/undergraduate/tuition-fee-and-financial-support") == (
        "admissions_page"
    )
    assert infer_source_kind(
        "https://scholarships.vinuni.edu.vn/vingroup-science-and-technology-scholarship/"
    ) == "scholarship_page"
    assert infer_source_kind("https://cecs.vinuni.edu.vn/undergraduate/computer-science/") == "program_page"
    # ...but MARKETING/news pages on the expansion hosts fall to external_public_page (dropped by --student-only).
    assert infer_source_kind("https://cecs.vinuni.edu.vn/category/college-news/") == "external_public_page"
    assert infer_source_kind("https://admissions.vinuni.edu.vn/a-look-back-on-vinuni-open-day-2023/") == (
        "external_public_page"
    )
    assert infer_source_kind("https://admissions.vinuni.edu.vn/event/info-session-2025/") == "external_public_page"
    # College images are still dropped as image_asset (format check wins).
    assert infer_source_kind("https://cecs.vinuni.edu.vn/wp-content/uploads/2024/photo.jpg") == "image_asset"
    # College program slugs the first-segment gate previously missed (audit 2026-06-24): VI undergraduate
    # "bac-dai-hoc", the CHS MD program, the CECS undergrad-research program, and college faculty bios.
    assert infer_source_kind("https://cecs.vinuni.edu.vn/vi/bac-dai-hoc/chuong-trinh-cu-nhan-cs/") == "program_page"
    assert infer_source_kind("https://chs.vinuni.edu.vn/medical-doctor-program/curriculum/") == "program_page"
    assert infer_source_kind("https://cecs.vinuni.edu.vn/uropcecs/eligibility-and-scope/") == "program_page"
    assert infer_source_kind("https://cecs.vinuni.edu.vn/vi/people/some-dean/") == "profile_page"


def test_infer_source_kind_mainsite_keeps_reference_sections_drops_news():
    # REGRESSION (2026-06-24 President bug): the main vinuni.edu.vn domain is official but news-heavy, so it
    # used to default-drop EVERYTHING to external_public_page — including /people/ leadership bios. The
    # reference sections must now be KEPT (high-value kinds --student-only retains)...
    assert infer_source_kind("https://vinuni.edu.vn/vi/people/tan-yap-peng-2/", title="GS. Tan Yap Peng") == (
        "profile_page"
    )
    assert infer_source_kind("https://vinuni.edu.vn/global_exchange/uiuc/") == "student_life_page"
    assert infer_source_kind("https://vinuni.edu.vn/student_life/vinuniversity-store/") == "student_life_page"
    assert infer_source_kind("https://vinuni.edu.vn/academics/home/") == "program_page"
    assert infer_source_kind("https://vinuni.edu.vn/vi/about-us/") == "about_page"
    # ...while genuine noise on the SAME domain still default-drops to external_public_page.
    assert infer_source_kind("https://vinuni.edu.vn/vi/category/tin-theo-chu-de/") == "external_public_page"
    assert infer_source_kind("https://vinuni.edu.vn/vi/tag/content-marketing/") == "external_public_page"
    assert infer_source_kind("https://vinuni.edu.vn/job/marketing-specialist/") == "external_public_page"
    assert infer_source_kind("https://vinuni.edu.vn/research/event/seminar/") == "external_public_page"
    # A top-level descriptive NEWS slug (not under a reference section) stays dropped.
    assert infer_source_kind("https://vinuni.edu.vn/vi/le-tot-nghiep-khoa-dau-tien/") == "external_public_page"
    # /people/ and exchange get sensible categories for routing/metadata.
    assert infer_category("https://vinuni.edu.vn/vi/people/tan-yap-peng-2/", "GS. Tan Yap Peng") == (
        "general",
        "people",
    )
    assert infer_category("https://vinuni.edu.vn/global_exchange/uiuc/", "") == ("student_services", "student_life")


def test_infer_source_kind_pdfs_keep_official_docs_drop_marketing():
    # REGRESSION (audit 2026-06-24): the old rule kept PDFs only on policy.vinuni, dropping official forms/
    # guides/curricula on other VinUni hosts. Student-service hosts keep ALL their PDFs...
    assert infer_source_kind("https://registrar.vinuni.edu.vn/wp-content/FRM07_Defer-Withdraw-Form.pdf") == (
        "registrar_page"
    )
    assert infer_source_kind("https://experience.vinuni.edu.vn/wp-content/STUDENT-GUIDE-2025-2026.pdf") == (
        "student_life_page"
    )
    assert infer_source_kind("https://policy.vinuni.edu.vn/wp-content/some-policy.pdf") == "policy_pdf"
    # ...admissions/college keep document-like PDFs (curricula, notices)...
    assert infer_source_kind("https://chs.vinuni.edu.vn/wp-content/BN_CurriculumFramework_Cohort.pdf") == (
        "program_page"
    )
    assert infer_source_kind("https://admissions.vinuni.edu.vn/wp-content/250924_MBA.pdf") == "admissions_page"
    # ...but marketing PDFs (poster/flyer) drop everywhere, and bare partner one-pagers on the main domain drop.
    assert infer_source_kind("https://admissions.vinuni.edu.vn/wp-content/VinUni-poster-AIEC.pdf") == (
        "external_public_page"
    )
    assert infer_source_kind("https://cecs.vinuni.edu.vn/wp-content/CECS-Affiliate-Program-Flyer.pdf") == (
        "external_public_page"
    )
    assert infer_source_kind("https://vinuni.edu.vn/wp-content/uploads/2019/04/UCLA.pdf") == "external_public_page"
    # A real guideline PDF on the main domain (document-named) is kept.
    assert infer_source_kind("https://vinuni.edu.vn/wp-content/VUNI.05_Workstudy-Program-Guideline.pdf") == (
        "program_page"
    )
