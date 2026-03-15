"""
VNTaxDB Taxonomy — Phân loại công văn thuế VN
Merged từ: Grok, ChatGPT, Gemini, Claude — 13/03/2026
Cấu trúc: SAC_THUE → chu_de → [chu_de_con]
"""

SAC_THUE_LABELS = {
    "TNDN": "Thuế Thu nhập doanh nghiệp (CIT)",
    "GTGT": "Thuế Giá trị gia tăng (VAT)",
    "TNCN": "Thuế Thu nhập cá nhân (PIT)",
    "TTDB": "Thuế Tiêu thụ đặc biệt (SCT)",
    "FCT": "Thuế Nhà thầu nước ngoài (FCT)",
    "GDLK": "Giao dịch liên kết / Chuyển giá",
    "QLT": "Quản lý thuế",
    "HOA_DON": "Hóa đơn điện tử",
    "HKD": "Hộ kinh doanh / Cá nhân kinh doanh",
    "XNK": "Thuế Xuất nhập khẩu / Hải quan",
    "TAI_NGUYEN_DAT": "Thuế Tài nguyên / Tiền thuê đất",
    "MON_BAI_PHI": "Lệ phí Môn bài / Phí & Lệ phí",
    "THUE_QT": "Thuế Quốc tế / Hiệp định thuế",
}

TAXONOMY = {
    "TNDN": {
        "Chi phí được trừ": [
            "Chi phí nhân viên & tiền lương",
            "Chi phí lãi vay & khống chế 30% EBITDA",
            "Chi phí khấu hao TSCĐ",
            "Chi phí quảng cáo, tiếp thị, khuyến mại",
            "Chi phí nghiên cứu & phát triển",
            "Trích lập dự phòng",
            "Chi phí không có chứng từ hợp lệ"
        ],
        "Doanh thu & ghi nhận": [
            "Thời điểm ghi nhận doanh thu",
            "Doanh thu từ bất động sản & xây dựng",
            "Doanh thu từ dịch vụ",
            "Doanh thu từ gia công & xuất khẩu",
            "Điều chỉnh giảm doanh thu (chiết khấu, trả lại)"
        ],
        "Thu nhập khác & điều chỉnh": [
            "Chuyển nhượng vốn & chứng khoán",
            "Chuyển nhượng bất động sản & dự án",
            "Thanh lý tài sản",
            "Chênh lệch tỷ giá",
            "Thu hồi công nợ & dự phòng"
        ],
        "Ưu đãi thuế TNDN": [
            "Ưu đãi theo địa bàn đầu tư",
            "Ưu đãi theo ngành nghề & lĩnh vực",
            "Ưu đãi dự án đầu tư mới & mở rộng",
            "Thuế tối thiểu toàn cầu (GMT/Pillar 2)",
            "Thu nhập không được ưu đãi"
        ],
        "Chuyển lỗ & bù trừ thu nhập": [
            "Xác định lỗ được chuyển",
            "Thứ tự chuyển lỗ",
            "Bù trừ ưu đãi & không ưu đãi",
            "Lỗ từ chuyển nhượng & bất động sản",
            "Chuyển lỗ khi tái cơ cấu"
        ],
        "Kê khai & quyết toán": [
            "Tạm nộp thuế hàng quý",
            "Quyết toán năm & điều chỉnh",
            "Khai bổ sung & điều chỉnh",
            "Phân bổ thu nhập giữa địa bàn",
            "Hồ sơ chứng minh chi phí"
        ],
        "Giao dịch đặc thù": [
            "Hợp đồng hợp tác kinh doanh (BCC)",
            "Khoản tài trợ & nhận tài trợ",
            "Chi hộ & thu hộ",
            "Thưởng & hỗ trợ từ đối tác",
            "Quỹ khoa học & công nghệ (KHCN)"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "GTGT": {
        "Đối tượng chịu thuế & thuế suất": [
            "Hàng hóa dịch vụ không chịu thuế GTGT",
            "Thuế suất 0% & điều kiện",
            "Thuế suất 5% & danh mục",
            "Thuế suất 10% (chuẩn)",
            "Chính sách giảm thuế tạm thời (8%)"
        ],
        "Giá tính thuế": [
            "Giá tính thuế hàng biếu tặng & tiêu dùng nội bộ",
            "Chiết khấu thương mại & giảm giá",
            "Hàng khuyến mại",
            "Giá tính thuế bất động sản & xây dựng",
            "Thời điểm xác định thuế GTGT"
        ],
        "Khấu trừ thuế đầu vào": [
            "Điều kiện hóa đơn chứng từ",
            "Điều kiện thanh toán không dùng tiền mặt",
            "Đầu vào dùng chung (chịu thuế & không chịu thuế)",
            "Khấu trừ TSCĐ & dự án đầu tư",
            "Khai bổ sung thuế đầu vào"
        ],
        "Hoàn thuế GTGT": [
            "Hoàn thuế xuất khẩu",
            "Hoàn thuế dự án đầu tư mới",
            "Hoàn thuế khi chuyển đổi & chấm dứt",
            "Kiểm tra trước hoàn & thanh tra sau hoàn",
            "Hồ sơ & thời hạn hoàn thuế"
        ],
        "Xuất khẩu & DNCX": [
            "Điều kiện áp dụng thuế suất 0%",
            "Bán vào doanh nghiệp chế xuất (DNCX)",
            "Gia công cho nước ngoài",
            "Dịch vụ xuất khẩu",
            "Chứng từ thanh toán & hải quan"
        ],
        "Kê khai & điều chỉnh": [
            "Kê khai theo tháng & quý",
            "Kê khai GTGT vãng lai ngoại tỉnh",
            "Khai bổ sung & xử lý sai sót",
            "Bù trừ số thuế còn được khấu trừ",
            "Rủi ro kê khai sai chỉ tiêu"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "TNCN": {
        "Thu nhập từ tiền lương & tiền công": [
            "Phụ cấp & trợ cấp không tính thu nhập chịu thuế",
            "Lợi ích bằng hiện vật (nhà ở, học phí, xe)",
            "Tiền thưởng & cổ phiếu thưởng (ESOP)",
            "Thu nhập từ hợp đồng dịch vụ & môi giới"
        ],
        "Giảm trừ gia cảnh": [
            "Giảm trừ bản thân",
            "Đăng ký & hồ sơ người phụ thuộc",
            "Giảm trừ bảo hiểm & hưu trí tự nguyện",
            "Giảm trừ từ thiện & nhân đạo"
        ],
        "Cư trú & hiệp định thuế": [
            "Xác định 183 ngày & tình trạng cư trú",
            "Kỳ tính thuế năm đầu & năm cuối",
            "Áp dụng hiệp định tránh đánh thuế hai lần (DTA)",
            "Chứng nhận cư trú & thủ tục DTA",
            "Khấu trừ thuế cá nhân không cư trú"
        ],
        "Thu nhập từ đầu tư & chuyển nhượng": [
            "Chuyển nhượng vốn góp & cổ phần",
            "Chuyển nhượng bất động sản",
            "Thừa kế & quà tặng BĐS, chứng khoán",
            "Cổ tức & lợi tức từ góp vốn",
            "Thu nhập từ trái phiếu & quỹ đầu tư"
        ],
        "Quyết toán & hoàn thuế": [
            "Ủy quyền quyết toán thuế TNCN",
            "Quyết toán tự thực hiện",
            "Hoàn thuế & bù trừ nộp thừa",
            "Khai thuế cho cá nhân kinh doanh khoán"
        ],
        "Thu nhập đặc thù": [
            "KOL, streamer & thu nhập từ mạng xã hội",
            "Thu nhập từ bản quyền & nhượng quyền",
            "Thu nhập từ trúng thưởng",
            "Thu nhập từ nông nghiệp & miễn thuế"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "TTDB": {
        "Đối tượng chịu thuế": [
            "Rượu, bia",
            "Thuốc lá & sản phẩm có nicotine",
            "Ô tô & xe điện",
            "Xăng dầu",
            "Dịch vụ (Golf, Casino, Karaoke, Massage)"
        ],
        "Giá tính thuế": [
            "Giá tại cơ sở sản xuất & nhập khẩu",
            "Giá qua công ty con/trung gian",
            "Trừ giá trị vỏ bao bì",
            "Điều chỉnh giá tối thiểu"
        ],
        "Khấu trừ & hoàn thuế": [
            "Khấu trừ TTĐB đầu vào (nguyên liệu)",
            "Hoàn thuế hàng tạm nhập tái xuất",
            "Hoàn thuế xuất khẩu"
        ],
        "Kê khai & nộp thuế": [
            "Kỳ kê khai & hồ sơ",
            "Nộp thuế điện tử",
            "Khai bổ sung & điều chỉnh"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "FCT": {
        "Đối tượng & phạm vi áp dụng": [
            "Dịch vụ cung cấp tại Việt Nam vs tiêu dùng ngoài VN",
            "Cung cấp hàng hóa kèm dịch vụ (Incoterms)",
            "Thương mại điện tử & nền tảng số xuyên biên giới",
            "Chuyển giao công nghệ & bản quyền (royalty)",
            "Hợp đồng xây dựng & EPC"
        ],
        "Phương pháp tính thuế": [
            "Phương pháp trực tiếp (tỷ lệ % ấn định)",
            "Phương pháp khấu trừ (kê khai)",
            "Phương pháp hỗn hợp",
            "Xác định Net vs Gross trong hợp đồng"
        ],
        "Thuế suất FCT": [
            "Tỷ lệ GTGT nhà thầu theo loại dịch vụ",
            "Tỷ lệ TNDN nhà thầu (bản quyền, dịch vụ, lãi vay)",
            "Thuế suất TNCN nhà thầu cá nhân"
        ],
        "Hiệp định tránh đánh thuế (DTA)": [
            "Miễn giảm thuế theo DTA",
            "Khái niệm cơ sở thường trú (PE)",
            "Beneficial owner & chống lạm dụng DTA",
            "Hồ sơ & thủ tục áp dụng DTA"
        ],
        "Kê khai & nộp thuế": [
            "Trách nhiệm khấu trừ & kê khai của bên VN",
            "Thời hạn kê khai từng lần phát sinh",
            "Hoàn thuế nhà thầu nộp thừa"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "GDLK": {
        "Xác định bên liên kết": [
            "Quan hệ sở hữu vốn & điều hành",
            "Quan hệ vay mượn & bảo lãnh",
            "Các trường hợp liên kết đặc thù (NĐ 132)",
            "Ngưỡng trọng yếu & miễn kê khai"
        ],
        "Phương pháp xác định giá": [
            "Phương pháp so sánh giá giao dịch độc lập (CUP)",
            "Phương pháp giá bán lại (RPM)",
            "Phương pháp chi phí cộng lãi (CPM)",
            "Phương pháp so sánh lợi nhuận (TNMM)",
            "Phương pháp tách lợi nhuận (PSM)"
        ],
        "Hồ sơ chuyển giá": [
            "Hồ sơ quốc gia (Local File)",
            "Hồ sơ tập đoàn (Master File)",
            "Báo cáo lợi nhuận liên quốc gia (CbCR)",
            "Thời hạn & yêu cầu lưu giữ hồ sơ"
        ],
        "Khống chế chi phí lãi vay": [
            "Tỷ lệ 30% EBITDA theo NĐ 132",
            "Cách tính EBITDA",
            "Chuyển tiếp lãi vay vượt mức sang năm sau",
            "Ngành đặc thù được miễn áp dụng"
        ],
        "APA & thanh tra": [
            "APA đơn phương & song phương",
            "Quy trình đàm phán & gia hạn APA",
            "Thanh tra & ấn định thuế chuyển giá",
            "Xử phạt vi phạm giao dịch liên kết"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "QLT": {
        "Đăng ký thuế": [
            "Cấp & quản lý mã số thuế (MST)",
            "Thay đổi thông tin đăng ký thuế",
            "Chấm dứt & khôi phục MST",
            "MST cá nhân & người phụ thuộc"
        ],
        "Kê khai thuế": [
            "Kê khai tháng, quý, năm & từng lần phát sinh",
            "Khai bổ sung & điều chỉnh",
            "Gia hạn nộp thuế & kê khai",
            "Kê khai điện tử"
        ],
        "Nộp thuế": [
            "Thời hạn nộp theo từng sắc thuế",
            "Tiền chậm nộp (0.03%/ngày)",
            "Bù trừ & xử lý nộp thừa",
            "Nộp thuế điện tử & ủy nhiệm thu"
        ],
        "Hoàn thuế": [
            "Hoàn thuế GTGT",
            "Hoàn thuế TNCN & nhà thầu",
            "Phân loại hồ sơ (kiểm tra trước/hoàn trước)",
            "Thời hạn giải quyết hoàn thuế"
        ],
        "Thanh tra & kiểm tra": [
            "Thanh tra tại trụ sở người nộp thuế",
            "Kiểm tra hồ sơ tại cơ quan thuế",
            "Quyền & nghĩa vụ khi bị thanh tra",
            "Truy thu & xử lý sau thanh tra"
        ],
        "Xử phạt vi phạm": [
            "Phạt chậm nộp tờ khai & chậm nộp thuế",
            "Phạt khai sai dẫn đến thiếu thuế",
            "Phạt trốn thuế & gian lận",
            "Tình tiết giảm nhẹ & tăng nặng",
            "Thời hiệu xử phạt"
        ],
        "Cưỡng chế & nợ thuế": [
            "Các biện pháp cưỡng chế nợ thuế",
            "Tạm hoãn xuất cảnh do nợ thuế",
            "Khoanh nợ & xóa nợ thuế",
            "Công khai thông tin nợ thuế"
        ],
        "Khiếu nại & khởi kiện": [
            "Quy trình khiếu nại quyết định thuế",
            "Khởi kiện hành chính về thuế",
            "Thời hiệu & thẩm quyền giải quyết"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "HOA_DON": {
        "Đăng ký & phát hành": [
            "Đăng ký sử dụng HĐĐT có mã & không có mã CQT",
            "Hóa đơn khởi tạo từ máy tính tiền",
            "Ủy nhiệm lập hóa đơn điện tử",
            "Chuyển đổi từ hóa đơn giấy sang điện tử"
        ],
        "Lập hóa đơn điện tử": [
            "Thời điểm lập hóa đơn theo từng nghiệp vụ",
            "Nội dung bắt buộc trên hóa đơn",
            "Hóa đơn cho hàng khuyến mại & biếu tặng",
            "Hóa đơn dịch vụ liên tục (điện, nước, viễn thông)",
            "Hóa đơn ngoại tệ & quy đổi VND"
        ],
        "Xử lý sai sót hóa đơn": [
            "Hóa đơn điều chỉnh",
            "Hóa đơn thay thế",
            "Hủy hóa đơn điện tử",
            "Thông báo sai sót (Mẫu 04/SS-HĐĐT)",
            "Xử lý hóa đơn có mã CQT bị sai"
        ],
        "Hóa đơn đặc thù": [
            "Hóa đơn xuất khẩu",
            "Hóa đơn bất động sản (thu tiền trước)",
            "Hóa đơn xây dựng & lắp đặt",
            "Hóa đơn bán hàng qua sàn TMĐT",
            "Hóa đơn góp vốn bằng tài sản"
        ],
        "Lưu trữ & tra cứu": [
            "Chuyển đổi HĐĐT sang hóa đơn giấy",
            "Lưu trữ hóa đơn (thời hạn & phương thức)",
            "Tra cứu & xác thực hóa đơn trên hệ thống CQT",
            "Rủi ro hóa đơn từ doanh nghiệp bỏ trốn"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "HKD": {
        "Phương pháp tính thuế": [
            "Thuế khoán (doanh thu khoán & mức thuế khoán)",
            "Kê khai thuế theo từng lần phát sinh",
            "Kê khai thuế theo quý",
            "Ngưỡng doanh thu 100 triệu/năm miễn thuế",
            "Chuyển đổi lên doanh nghiệp khi vượt ngưỡng"
        ],
        "Thuế GTGT & TNCN HKD": [
            "Tỷ lệ thuế GTGT theo ngành nghề",
            "Tỷ lệ thuế TNCN theo ngành nghề",
            "Doanh thu tính thuế khoán & điều chỉnh",
            "Miễn thuế HKD dưới ngưỡng doanh thu"
        ],
        "Cho thuê tài sản": [
            "Thuế GTGT & TNCN từ cho thuê nhà, mặt bằng",
            "Kê khai thuê tài sản (1 lần vs hàng kỳ)",
            "Trách nhiệm kê khai của bên thuê",
            "Ngưỡng doanh thu miễn thuế cho thuê"
        ],
        "Kinh doanh qua nền tảng số": [
            "Bán hàng online & sàn thương mại điện tử",
            "Thu nhập từ KOL, streamer, mạng xã hội",
            "Trách nhiệm của sàn TMĐT trong kê khai"
        ],
        "Hóa đơn & sổ sách HKD": [
            "Hóa đơn điện tử cấp theo từng lần",
            "Chế độ kế toán đơn giản",
            "Đăng ký & chấm dứt kinh doanh"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "XNK": {
        "Thuế xuất khẩu & nhập khẩu": [
            "Biểu thuế & phân loại mã HS",
            "Giá tính thuế nhập khẩu (trị giá hải quan)",
            "Thuế suất ưu đãi đặc biệt (FTA: CPTPP, EVFTA, RCEP)",
            "Thuế tự vệ, chống bán phá giá, chống trợ cấp",
            "Thuế xuất khẩu tài nguyên & khoáng sản"
        ],
        "Miễn giảm hoàn thuế XNK": [
            "Miễn thuế dự án đầu tư & gia công xuất khẩu",
            "Miễn thuế hàng tạm nhập tái xuất",
            "Hoàn thuế nhập khẩu cho hàng xuất khẩu",
            "Hoàn thuế do nhầm lẫn & nộp thừa"
        ],
        "Thủ tục hải quan": [
            "Khai báo hải quan điện tử (VNACCS/VCIS)",
            "Phân luồng kiểm tra (xanh, vàng, đỏ)",
            "Khai bổ sung & hủy tờ khai hải quan",
            "Kiểm tra sau thông quan"
        ],
        "Xuất xứ hàng hóa (C/O)": [
            "Quy tắc xuất xứ theo các FTA",
            "Tự chứng nhận xuất xứ",
            "Kiểm tra & xác minh C/O"
        ],
        "DNCX & khu phi thuế quan": [
            "Chính sách thuế DNCX",
            "Bán hàng nội địa vào khu chế xuất",
            "Hàng gửi kho ngoại quan"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "TAI_NGUYEN_DAT": {
        "Thuế tài nguyên": [
            "Đối tượng chịu thuế tài nguyên",
            "Sản lượng & giá tính thuế tài nguyên",
            "Thuế suất theo loại tài nguyên",
            "Miễn giảm thuế tài nguyên",
            "Kê khai & nộp thuế tài nguyên"
        ],
        "Tiền thuê đất & mặt nước": [
            "Đơn giá thuê đất hàng năm vs thuê 1 lần",
            "Miễn giảm tiền thuê đất (dự án ưu đãi)",
            "Điều chỉnh đơn giá & chu kỳ ổn định",
            "Thuê đất khi chuyển mục đích sử dụng"
        ],
        "Tiền sử dụng đất": [
            "Xác định tiền sử dụng đất khi giao đất",
            "Phương pháp xác định giá đất",
            "Miễn giảm tiền sử dụng đất",
            "Nộp tiền sử dụng đất khi cấp sổ đỏ"
        ],
        "Thuế sử dụng đất phi nông nghiệp": [
            "Đối tượng chịu thuế & miễn thuế",
            "Giá tính thuế & thuế suất",
            "Kê khai & nộp thuế"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    },
    "MON_BAI_PHI": {
        "Lệ phí môn bài": [
            "Mức thu theo vốn điều lệ & doanh thu",
            "Miễn lệ phí môn bài năm đầu & hộ nhỏ",
            "Môn bài cho chi nhánh, VPĐD, địa điểm KD",
            "Kê khai & nộp lệ phí môn bài"
        ],
        "Lệ phí trước bạ": [
            "Lệ phí trước bạ nhà đất",
            "Lệ phí trước bạ ô tô & xe máy",
            "Giá tính lệ phí trước bạ",
            "Miễn giảm lệ phí trước bạ"
        ],
        "Phí & lệ phí khác": [
            "Phí bảo vệ môi trường (nước thải, khí thải)",
            "Phí thẩm định & đăng ký",
            "Lệ phí hải quan",
            "Danh mục phí & lệ phí theo Luật"
        ],
        "Khác": ["khác", "vướng mắc", "hướng dẫn chung", "tư vấn"],
    }
    "THUE_QT": {
        "Hiệp định tránh đánh thuế hai lần (DTA)": [
            "Cơ sở thường trú (Permanent Establishment - PE)",
            "Phân bổ quyền đánh thuế giữa các quốc gia",
            "Miễn giảm thuế theo DTA",
            "Beneficial owner & chống lạm dụng Hiệp định",
            "Thủ tục xin áp dụng DTA & chứng nhận cư trú",
            "Tham vấn song phương (MAP) & APA quốc tế",
        ],
        "Thuế tối thiểu toàn cầu (Pillar 2 / GMT)": [
            "Quy tắc GloBE (Global Anti-Base Erosion)",
            "Thuế tối thiểu 15% (QDMTT)",
            "Income Inclusion Rule (IIR) & Undertaxed Profits Rule (UTPR)",
            "Doanh nghiệp thuộc diện áp dụng (doanh thu >750 triệu EUR)",
            "Nghị quyết 107/2023/QH15 & triển khai tại Việt Nam",
            "Ưu đãi đầu tư trong bối cảnh Pillar 2",
        ],
        "Cơ sở thường trú (Permanent Establishment)": [
            "PE theo mô hình OECD & UN",
            "PE xây dựng & dịch vụ (time threshold)",
            "Agency PE & Commissionnaire arrangement",
            "PE trong kinh tế số & DAPE",
            "Xác định thu nhập quy cho PE",
        ],
        "Miễn giảm thuế & tín thuế quốc tế": [
            "Phương pháp miễn thuế (Exemption method)",
            "Phương pháp tín thuế (Credit method)",
            "Tín thuế nước ngoài (Foreign Tax Credit - FTC)",
            "Giới hạn tín thuế & surplus/deficit",
        ],
        "Thuế TTTC & Tax Haven": [
            "Kiểm soát công ty nước ngoài (CFC rules)",
            "Hybrid mismatch arrangements",
            "Thin capitalisation & lãi vay liên kết quốc tế",
            "Substance requirements & shell company",
        ],
        "BEPS & chống tránh thuế quốc tế": [
            "BEPS Action Plan (15 Actions) — tổng quan",
            "Multilateral Instrument (MLI) & Việt Nam",
            "Country-by-Country Reporting (CbCR)",
            "Principal Purpose Test (PPT) & LOB clause",
            "Chuyển giá quốc tế & arm\'s length principle",
        ],
        "Thuế thu nhập cá nhân quốc tế": [
            "Xác định cư trú thuế cá nhân (183 ngày)",
            "Tie-breaker rules theo DTA",
            "Đánh thuế lương người nước ngoài tại VN",
            "Tín thuế nước ngoài cho cá nhân",
        ],
        "Khác": ["khác", "treaty shopping", "offshore", "hướng dẫn chung", "tư vấn quốc tế"],
    }
}


# Rule-based keywords cho phân loại tự động
CLASSIFICATION_RULES = {
    "TNDN": ["thu nhập doanh nghiệp", "tndn", "cit", "chi phí được trừ", "doanh thu tính thuế",
             "ưu đãi thuế", "chuyển lỗ", "khấu hao", "quyết toán doanh nghiệp"],
    "GTGT": ["giá trị gia tăng", "gtgt", "vat", "hóa đơn đầu vào", "khấu trừ thuế",
             "hoàn thuế gtgt", "thuế suất 0%", "thuế suất 5%", "thuế suất 10%"],
    "TNCN": ["thu nhập cá nhân", "tncn", "pit", "giảm trừ gia cảnh", "quyết toán thuế",
             "người phụ thuộc", "khấu trừ tại nguồn", "ủy quyền quyết toán"],
    "TTDB": ["tiêu thụ đặc biệt", "ttđb", "ttdb", "sct", "rượu bia", "thuốc lá", "ô tô"],
    "FCT":  ["nhà thầu nước ngoài", "nhà thầu", "fct", "foreign contractor",
             "dịch vụ từ nước ngoài", "royalty", "bản quyền", "lãi vay nước ngoài"],
    "GDLK": ["giao dịch liên kết", "chuyển giá", "transfer pricing", "apa",
             "bên liên kết", "nghị định 132", "cbcr", "lãi vay liên kết"],
    "QLT":  ["quản lý thuế", "kê khai", "nộp thuế", "hoàn thuế", "thanh tra thuế",
             "kiểm tra thuế", "xử phạt", "cưỡng chế", "khiếu nại", "mã số thuế"],
    "HOA_DON": ["hóa đơn điện tử", "hđđt", "hóa đơn gtgt", "mã cơ quan thuế",
               "xuất hóa đơn", "hóa đơn sai sót", "hóa đơn thay thế"],
    "HKD":  ["hộ kinh doanh", "cá nhân kinh doanh", "thuế khoán", "hộ cá thể",
             "cho thuê nhà", "cho thuê tài sản", "kol", "streamer", "sàn tmđt"],
    "XNK":  ["xuất nhập khẩu", "hải quan", "nhập khẩu", "xuất khẩu", "mã hs",
             "trị giá hải quan", "thông quan", "c/o", "xuất xứ", "fta"],
    "TAI_NGUYEN_DAT": ["tài nguyên", "tiền thuê đất", "tiền sử dụng đất",
                       "thuê mặt nước", "khoáng sản", "đất đai"],
    "MON_BAI_PHI": ["môn bài", "lệ phí môn bài", "phí", "lệ phí", "trước bạ",
                    "lệ phí trước bạ", "phí bảo vệ môi trường"],
    "THUE_QT": ["hiệp định", "dta", "treaty", "thuế quốc tế", "pillar 2", "pillar2", "globe",
                "beps", "oecd", "cfc", "cơ sở thường trú", "permanent establishment",
                "tín thuế nước ngoài", "foreign tax credit", "qdmtt", "thuế tối thiểu toàn cầu",
                "tax haven", "offshore", "cbcr", "mli", "nghị quyết 107"],
}

def classify_document(title: str, content: str = "") -> list[str]:
    """Rule-based classification — returns list of sac_thue codes"""
    text = (title + " " + content).lower()
    result = []
    for code, keywords in CLASSIFICATION_RULES.items():
        if any(kw in text for kw in keywords):
            result.append(code)
    return result if result else ["QLT"]  # default: quản lý thuế

# CHU_DE_RULES: build từ TAXONOMY để dùng cho classify
CHU_DE_RULES = {}
for _sac_thue, _chu_des in TAXONOMY.items():
    CHU_DE_RULES[_sac_thue] = {}
    for _chu_de, _chu_de_cons in _chu_des.items():
        _keywords = [_chu_de.lower()] + [c.lower() for c in _chu_de_cons]
        CHU_DE_RULES[_sac_thue][_chu_de] = _keywords


def classify_chu_de(title: str, sac_thue_list: list, content: str = "") -> list:
    """Classify chu_de cho CV dựa trên sac_thue.
    Returns list of chu_de strings. Fallback: ['Khác'] nếu không match.
    """
    text = (title + " " + content).lower()
    result = []
    seen = set()
    for sac_thue in sac_thue_list:
        if sac_thue not in CHU_DE_RULES:
            continue
        for chu_de, keywords in CHU_DE_RULES[sac_thue].items():
            if chu_de == "Khác":
                continue
            if any(kw in text for kw in keywords) and chu_de not in seen:
                seen.add(chu_de)
                result.append(chu_de)
    return result if result else ["Khác"]
