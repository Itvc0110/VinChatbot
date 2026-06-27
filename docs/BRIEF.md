AI20K-Build-Cohort-2-Team-050
Project Brief — AI Trợ Lý Hỏi Đáp Học Vụ & Hỗ Trợ Sinh Viên 24/7
1. Brief
1.1. Tên project
AI Trợ Lý Hỏi Đáp Học Vụ & Hỗ Trợ Sinh Viên 24/7
1.2. Bối cảnh bài toán
Trong môi trường đại học, sinh viên thường xuyên có rất nhiều câu hỏi liên quan đến học vụ và dịch vụ sinh viên, ví dụ như đăng ký môn học, học phí, lịch thi, quy chế học tập, quy trình xin giấy xác nhận, bảo lưu, chuyển ngành, khiếu nại học vụ hoặc các thủ tục hành chính khác. Tuy nhiên, các thông tin này thường nằm rải rác trong nhiều tài liệu, trang web, file PDF, thông báo hoặc quy định nội bộ. Điều này khiến sinh viên mất thời gian tìm kiếm, dễ đọc nhầm thông tin cũ hoặc không biết nên hỏi đúng bộ phận nào.
Bên cạnh đó, phòng đào tạo và các đơn vị hỗ trợ sinh viên thường chỉ làm việc trong giờ hành chính. Khi sinh viên cần hỗ trợ ngoài giờ hoặc vào các thời điểm cao điểm như đăng ký môn, đóng học phí, thi cuối kỳ, xét tốt nghiệp, số lượng câu hỏi tăng mạnh và có thể gây quá tải cho đội ngũ hỗ trợ.
Project này hướng tới xây dựng một trợ lý AI học vụ 24/7, có khả năng trả lời câu hỏi của sinh viên dựa trên các tài liệu chính thức của trường, trích dẫn nguồn rõ ràng, hướng dẫn quy trình từng bước và từ chối trả lời khi không đủ dữ liệu đáng tin cậy. Trọng tâm MVP là hỏi đáp học vụ dựa trên tài liệu quy định và hướng dẫn chính thức. Cá nhân hóa theo tình trạng sinh viên được xem là phần mở rộng sau khi có thể tích hợp với hệ thống nội bộ như SIS hoặc tài khoản sinh viên.
1.3. Problem Statement
Sinh viên cần một kênh hỗ trợ học vụ nhanh, chính xác và có thể truy cập 24/7, nhưng hiện tại thông tin học vụ thường phân tán, khó tra cứu và phụ thuộc nhiều vào nhân sự hỗ trợ trong giờ hành chính. Điều này dẫn đến việc sinh viên chờ lâu, hỏi lặp lại, tìm sai thông tin hoặc không biết quy trình cần thực hiện.
1.4. Mục tiêu sản phẩm
Mục tiêu của sản phẩm là xây dựng một web/app hoàn chỉnh cho phép sinh viên đặt câu hỏi học vụ bằng ngôn ngữ tự nhiên và nhận câu trả lời có căn cứ từ tài liệu chính thức. Hệ thống cần có khả năng:
Trả lời câu hỏi về quy chế, học phí, lịch học, lịch thi, thủ tục học vụ và các hướng dẫn sinh viên.
Trích dẫn nguồn tài liệu chính thức để người dùng có thể kiểm chứng.
Hướng dẫn quy trình thủ tục theo từng bước.
Có guardrail để không bịa thông tin khi dữ liệu không đủ rõ, bảo mật dữ liệu nhạy cảm và bảo vệ bảo mật hệ thống.
Có đăng nhập, phân quyền cơ bản và quản lý người dùng. (dự định)
Có giao diện web/chat UI hoàn chỉnh và được deploy online.
1.5. Phạm vi MVP
MVP tập trung vào hỏi đáp học vụ dựa trên tài liệu chính thức. Các tính năng cá nhân hóa như trả lời theo ngành học, khóa học, số tín chỉ, trạng thái học phí hoặc tình trạng học tập của từng sinh viên chỉ được xem là extension khi có quyền tích hợp với hệ thống nội bộ.
Phạm vi MVP bao gồm:
Chatbot hỏi đáp học vụ dựa trên RAG.
Tìm kiếm và truy xuất tài liệu chính thức.
Trích dẫn nguồn trong câu trả lời.
Hướng dẫn quy trình thủ tục cơ bản.
Đăng nhập và phân quyền người dùng.
Dashboard quản trị tài liệu ở mức cơ bản.
Deploy web/app online.
Không nằm trong phạm vi MVP:
Tích hợp thật với SIS/Canvas ở mức production.
Cá nhân hóa sâu theo hồ sơ sinh viên thật.
Tự động thực hiện thủ tục thay sinh viên.
Thay thế hoàn toàn phòng đào tạo hoặc nhân sự học vụ.
Trả lời các câu hỏi không có nguồn chính thức.
2. PRD — Product Requirements Document
2.1. Người dùng mục tiêu
Sinh viên
Sinh viên là người dùng chính của hệ thống. Họ cần hỏi nhanh các vấn đề học vụ như đăng ký môn, lịch thi, quy chế, học phí, quy trình xin xác nhận, bảo lưu hoặc các thông tin liên quan đến dịch vụ sinh viên.
Nhân sự phòng đào tạo / Student Services
Nhân sự học vụ có thể dùng hệ thống để giảm số lượng câu hỏi lặp lại, kiểm tra câu trả lời của bot và cập nhật nguồn tài liệu.
Admin hệ thống
Admin chịu trách nhiệm quản lý tài liệu, theo dõi log câu hỏi, cập nhật dữ liệu và kiểm tra các trường hợp bot không trả lời được.
2.2. User Stories ưu tiên cho MVP
User Story 1 — Hỏi đáp học vụ có trích dẫn nguồn
Là một sinh viên, tôi muốn hỏi các câu hỏi liên quan đến học vụ bằng ngôn ngữ tự nhiên để nhận được câu trả lời nhanh, chính xác và có dẫn nguồn từ tài liệu chính thức.
Ví dụ câu hỏi:
“Hạn đăng ký môn là khi nào?”
“Nếu em muốn drop course thì cần làm gì?”
“Quy định về học phí như thế nào?”
“Em có thể xin bảo lưu học tập không?”
“Nếu vi phạm academic integrity thì xử lý thế nào?”
Acceptance Criteria:
Người dùng có thể nhập câu hỏi trong giao diện chat.
Hệ thống trả lời dựa trên tài liệu đã được index.
Câu trả lời có ít nhất một nguồn trích dẫn nếu có dữ liệu.
Nếu không tìm thấy nguồn phù hợp, hệ thống phải nói rõ là không đủ thông tin thay vì tự bịa.
Câu trả lời ngắn gọn, dễ hiểu và có thể kèm bước tiếp theo.
User Story 2 — Hướng dẫn quy trình thủ tục từng bước
Là một sinh viên, tôi muốn được hướng dẫn từng bước khi cần thực hiện một thủ tục học vụ để biết phải chuẩn bị gì, nộp ở đâu và liên hệ bộ phận nào.
Ví dụ câu hỏi:
“Em muốn xin giấy xác nhận sinh viên thì làm như thế nào?”
“Quy trình xin bảo lưu gồm những bước nào?”
“Nếu muốn khiếu nại điểm thì cần làm gì?”
“Em cần làm gì để đăng ký lại môn?”
Acceptance Criteria:
Hệ thống nhận diện câu hỏi dạng “thủ tục/quy trình”.
Câu trả lời được trình bày thành các bước rõ ràng.
Có thông tin về điều kiện, tài liệu cần chuẩn bị, nơi nộp hoặc kênh liên hệ nếu tài liệu có đề cập.
Có dẫn nguồn từ tài liệu chính thức.
Nếu quy trình không đủ rõ, bot đề xuất người dùng liên hệ bộ phận phụ trách và cung cấp tóm tắt vấn đề.
User Story 3 — Đăng nhập và phân quyền cơ bản
Là người dùng hệ thống, tôi muốn đăng nhập để hệ thống phân biệt vai trò sinh viên và admin, từ đó giới hạn quyền truy cập phù hợp.
Vai trò:
Student: chat với bot, xem lịch sử hội thoại của bản thân.
Admin: quản lý tài liệu, xem log câu hỏi, kiểm tra câu hỏi chưa trả lời được.
Acceptance Criteria:
Có màn hình đăng nhập.
Có phân quyền Student/Admin.
Student không truy cập được trang quản trị.
Admin có thể xem danh sách tài liệu và trạng thái index.
Hệ thống lưu lịch sử chat cơ bản.
User Story 4 — Quản lý tài liệu nguồn
Là admin, tôi muốn upload hoặc cập nhật tài liệu học vụ để chatbot có thể trả lời dựa trên phiên bản mới nhất.
Acceptance Criteria:
Admin có thể upload file PDF, DOCX hoặc thêm URL tài liệu.
Hệ thống lưu metadata: tên tài liệu, loại tài liệu, ngày cập nhật, nguồn.
Hệ thống xử lý tài liệu thành chunks.
Hệ thống tạo embedding và lưu vào vector database.
Admin có thể xem trạng thái: pending, indexed, failed.
User Story N — Sẽ được team update trong quá trình phát triển MVP
2.3. Functional Requirements
FR1 — Chat hỏi đáp
Hệ thống cần cung cấp giao diện chat cho sinh viên đặt câu hỏi. Chatbot cần trả lời bằng tiếng Việt hoặc tiếng Anh tùy theo ngôn ngữ câu hỏi. Câu trả lời phải dựa trên dữ liệu truy xuất được từ tài liệu chính thức.
FR2 — Retrieval-Augmented Generation
Hệ thống sử dụng RAG để tìm kiếm các đoạn tài liệu liên quan trước khi sinh câu trả lời. Pipeline gồm: nhận câu hỏi, tạo embedding, tìm top-k chunks, rerank nếu cần, đưa context vào LLM, sinh câu trả lời có dẫn nguồn.
FR3 — Citation
Mỗi câu trả lời có thông tin từ tài liệu phải đi kèm nguồn tham chiếu. Citation tối thiểu cần có tên tài liệu, section hoặc đoạn liên quan, và link nếu có.
FR4 — Guardrail chống hallucination
Nếu hệ thống không tìm thấy tài liệu đủ liên quan, bot phải trả lời theo hướng: “Hiện tại tôi chưa tìm thấy thông tin chính thức đủ rõ để trả lời câu hỏi này.” Bot không được tự suy đoán quy định, học phí, hạn nộp hoặc quy trình.
FR5 — Step-by-step procedure answer
Với câu hỏi về thủ tục, bot cần trả lời theo format: điều kiện, các bước thực hiện, tài liệu cần chuẩn bị, nơi liên hệ, lưu ý và nguồn.
FR6 — User authentication
Hệ thống cần có đăng nhập và phân quyền cơ bản. Người dùng có thể đăng nhập bằng email/password ở MVP. Extension có thể tích hợp SSO hoặc tài khoản sinh viên.
FR7 — Admin document management
Admin có thể upload, xóa, cập nhật hoặc re-index tài liệu. Admin có thể xem trạng thái xử lý tài liệu và danh sách tài liệu đang được dùng bởi hệ thống.
FR8 — Chat history
Hệ thống lưu lịch sử hội thoại theo user để người dùng có thể xem lại các câu hỏi cũ. Admin có thể xem log ở mức tổng hợp để cải thiện dữ liệu, nhưng cần tránh hiển thị thông tin cá nhân nhạy cảm nếu không cần thiết.
2.4. Non-functional Requirements
Accuracy: Câu trả lời phải dựa trên nguồn chính thức, có citation.
Latency: Thời gian phản hồi mục tiêu dưới 5–8 giây cho MVP.
Availability: Ứng dụng được deploy online và có URL truy cập.
Security: Có xác thực người dùng và phân quyền cơ bản.
Privacy: Không thu thập dữ liệu cá nhân ngoài phạm vi cần thiết.
Maintainability: Dữ liệu nguồn có thể cập nhật và re-index.
Scalability: Kiến trúc có thể mở rộng sang nhiều loại tài liệu và nhiều nhóm người dùng.
2.5. Data Sources
Nguồn dữ liệu trọng tâm cho MVP là các tài liệu chính thức liên quan đến học vụ và hỗ trợ sinh viên, bao gồm:
Academic regulations.
Student handbook hoặc student guide nếu có.
Academic calendar.
Tuition and financial regulations.
Examination regulations.
Course registration/drop/withdrawal policy.
Academic integrity policy.
Student code of conduct.
Registry forms and student services procedures.
FAQ hoặc thông báo chính thức từ trường.
Dữ liệu cần được xử lý theo pipeline:
Crawl hoặc upload tài liệu.
Extract text từ HTML/PDF/DOCX.
Clean nội dung.
Chunking theo section, heading hoặc semantic boundary.
Gắn metadata: source, document type, issued date, updated date, URL, section.
Tạo embedding.
Lưu vào vector database.
Retrieval khi người dùng đặt câu hỏi.
Sinh câu trả lời kèm citation.
2.6. Suggested Tech Stack
Frontend
React hoặc Next.js.
Tailwind CSS.
Chat UI dạng web app.
Role-based UI cho Student và Admin.
Backend
FastAPI.
Python.
REST API cho chat, authentication, document upload, document indexing.
etc.
AI/RAG Layer
OpenAI hoặc Claude cho LLM.
Embedding model: OpenAI embedding hoặc multilingual embedding model.
Vector database: ChromaDB, Qdrant, Pinecone hoặc pgvector.
Optional reranking: Cohere Rerank hoặc cross-encoder reranker.
Prompt guardrail để giới hạn câu trả lời theo context.
etc.
Database
PostgreSQL cho user, role, chat history, metadata tài liệu.
Vector DB cho chunks và embeddings (dự định là qdrant).
Deployment
Frontend: Vercel (dự tính).
Backend: Render, Railway, Fly.io hoặc cloud server.
Database: Supabase/PostgreSQL.
Object storage: Supabase Storage hoặc S3-compatible storage cho file tài liệu.
2.7. Success Metrics
Tỷ lệ câu trả lời có citation hợp lệ.
Tỷ lệ câu hỏi được trả lời đúng dựa trên bộ test case.
Tỷ lệ câu hỏi bot từ chối đúng khi không có nguồn.
Thời gian phản hồi trung bình.
Số lượng câu hỏi được xử lý mà không cần chuyển tiếp cho người thật.
Mức độ hài lòng của người dùng trong demo/test.
etc.
3. Wireframe / UI
3.1. Màn hình đăng nhập
Mục tiêu: Cho phép người dùng đăng nhập và phân quyền.
Thành phần UI:
Logo hoặc tên sản phẩm.
Input email.
Input password.
Button “Login”.
Link “Forgot password” nếu cần.
Thông báo lỗi khi đăng nhập sai.
Luồng:
Người dùng nhập email/password.
Backend xác thực.
Nếu role là Student, chuyển đến Chat Page.
Nếu role là Admin, chuyển đến Admin Dashboard.
3.2. Student Chat Page
Mục tiêu: Cho phép sinh viên hỏi đáp học vụ 24/7.
Layout đề xuất:
Sidebar trái:
New chat.
Chat history.
User profile.
Logout.
Main chat area:
Header: “AI Academic Assistant”.
Message list.
Input box.
Button send.
Quick prompt chips:
“Hỏi về đăng ký môn”
“Hỏi về học phí”
“Hỏi về lịch thi”
“Hỏi về quy chế học vụ”
“Hỏi về thủ tục sinh viên”
Answer card:
Câu trả lời chính.
Citation/source box.
Suggested next questions.
Feedback buttons: helpful / not helpful.
Ví dụ hiển thị câu trả lời:
Theo tài liệu học vụ, nếu sinh viên muốn drop course, sinh viên cần kiểm tra thời hạn drop course trong academic calendar và thực hiện theo quy trình đăng ký/hủy môn của phòng đào tạo.
Nguồn: Academic Calendar, Course Registration Policy.
3.3. Procedure Answer UI
Mục tiêu: Hiển thị câu trả lời dạng quy trình rõ ràng.
Format card:
Title: “Quy trình xin giấy xác nhận sinh viên”
Step 1: Kiểm tra điều kiện.
Step 2: Chuẩn bị thông tin/tài liệu.
Step 3: Nộp form hoặc liên hệ đơn vị phụ trách.
Step 4: Theo dõi kết quả.
Notes: Các lưu ý quan trọng.
Sources: Link/tên tài liệu chính thức.
3.4. Admin Dashboard
Mục tiêu: Cho phép admin quản lý tài liệu và theo dõi chất lượng bot.
Tabs chính:
Documents
Upload
Chat Logs
Unanswered Questions
Settings
Documents Tab
Hiển thị bảng tài liệu:
Document name.
Type.
Source URL.
Last updated.
Index status.
Number of chunks.
Actions: View, Re-index, Delete.
Upload Tab
Cho phép admin:
Upload PDF/DOCX.
Thêm URL.
Chọn document type.
Nhập mô tả.
Bấm “Index document”.
Chat Logs Tab
Hiển thị:
User question.
Bot answer.
Retrieved sources.
Feedback.
Timestamp.
Unanswered Questions Tab
Hiển thị các câu hỏi bot không trả lời được để admin biết tài liệu nào còn thiếu.
3.5. Wireframe dạng text
Login Page
​
Student Chat Page
​
Admin Dashboard
​
4. GitHub Repo
Repository:
https://github.com/AI20K-Build-Cohort-2/C2-App-050
4.1. Cấu trúc repo dự tính
​
4.2. README cần có
README nên bao gồm:
Project overview.
Problem statement.
Key features.
Tech stack.
System architecture.
Setup instructions.
Environment variables.
How to run frontend/backend.
Deployment URL.
Demo account.
Data sources.
Limitations.
Team members and contribution.
4.3. Deployment Requirement
Sản phẩm cần có URL truy cập online. Không chỉ nộp notebook, CLI script hoặc prototype chạy localhost. MVP cần có web/app hoàn chỉnh, đăng nhập, phân quyền cơ bản, giao diện UI/UX rõ ràng và quản lý user.
5. Extension sau MVP
Sau MVP, hệ thống có thể mở rộng theo các hướng:
Tích hợp SIS hoặc hệ thống sinh viên để cá nhân hóa câu trả lời theo ngành, khóa, năm học, số tín chỉ và trạng thái học vụ.
Tự động tạo ticket khi câu hỏi phức tạp cần chuyển cho nhân sự học vụ.
Tóm tắt hội thoại và chuyển tiếp cho phòng đào tạo.
Thêm notification/reminder cho deadline học vụ.
Thêm multilingual support cho sinh viên quốc tế.
Thêm evaluation dashboard để đo chất lượng RAG.
Xây dựng knowledge graph/GraphRAG nếu dữ liệu quy định trở nên phức tạp và cần suy luận nhiều bước giữa các văn bản.