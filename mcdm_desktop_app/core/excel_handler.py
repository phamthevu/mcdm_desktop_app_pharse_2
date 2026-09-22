import pandas as pd
from pathlib import Path

def generate_default_template(output_path: str = "templates/Config_Template.xlsx"):
    """Tự động sinh file Excel mẫu chuẩn cho hệ thống MCDM (gọn gàng, linh hoạt)."""
    
    # 1. Sheet Factors & Alternatives
    df_factors = pd.DataFrame([
        {"Type": "Factor", "Code": "C1", "Name": "Chi phí đầu tư (Cost)", "Description": "Tổng chi phí triển khai dự án"},
        {"Type": "Factor", "Code": "C2", "Name": "Thời gian hoàn thành (Time)", "Description": "Tiến độ thực hiện"},
        {"Type": "Factor", "Code": "C3", "Name": "Chất lượng kỹ thuật (Quality)", "Description": "Độ ổn định, đáp ứng kỹ thuật"},
        {"Type": "Factor", "Code": "C4", "Name": "Độ tin cậy của đối tác (Reliability)", "Description": "Uy tín và năng lực nhà cung cấp"},
        {"Type": "Alternative", "Code": "A1", "Name": "Phương án 1 (Vendor X)", "Description": "Thuê trọn gói giải pháp ngoài"},
        {"Type": "Alternative", "Code": "A2", "Name": "Phương án 2 (In-house)", "Description": "Tự phát triển nội bộ"},
        {"Type": "Alternative", "Code": "A3", "Name": "Phương án 3 (Hybrid)", "Description": "Thuê chuyên gia cố vấn và làm nội bộ"}
    ])

    # 2. Sheet Thang đo thông thường (Không có Z): Đúng 3 cột, Value điền tự do
    df_scale_standard = pd.DataFrame([
        {"Linguistic_Term": "Very Low", "Code": "VL", "Value": "0, 0, 0.25"},
        {"Linguistic_Term": "Low", "Code": "L", "Value": "0, 0.25, 0.5"},
        {"Linguistic_Term": "Medium", "Code": "M", "Value": "0.25, 0.5, 0.75"},
        {"Linguistic_Term": "High", "Code": "H", "Value": "0.5, 0.75, 1.0"},
        {"Linguistic_Term": "Very High", "Code": "VH", "Value": "0.75, 1.0, 1.0"}
    ])

    # 3. Sheet Thang đo Z-number: 6 cột (ghép 2 bộ 3 cột: Đánh giá A & Chắc chắn B)
    df_scale_z_number = pd.DataFrame([
        {
            "A_Linguistic_Term": "Very Low", "A_Code": "VL", "A_Value": "0, 0, 0.25",
            "B_Linguistic_Term": "Very Unlikely", "B_Code": "VU", "B_Value": "0, 0, 0.2"
        },
        {
            "A_Linguistic_Term": "Low", "A_Code": "L", "A_Value": "0, 0.25, 0.5",
            "B_Linguistic_Term": "Unlikely", "B_Code": "U", "B_Value": "0.1, 0.3, 0.5"
        },
        {
            "A_Linguistic_Term": "Medium", "A_Code": "M", "A_Value": "0.25, 0.5, 0.75",
            "B_Linguistic_Term": "Neutral", "B_Code": "N", "B_Value": "0.3, 0.5, 0.7"
        },
        {
            "A_Linguistic_Term": "High", "A_Code": "H", "A_Value": "0.5, 0.75, 1.0",
            "B_Linguistic_Term": "Likely", "B_Code": "Lk", "B_Value": "0.5, 0.7, 0.9"
        },
        {
            "A_Linguistic_Term": "Very High", "A_Code": "VH", "A_Value": "0.75, 1.0, 1.0",
            "B_Linguistic_Term": "Very Likely", "B_Code": "VLk", "B_Value": "0.8, 1.0, 1.0"
        }
    ])

    # 4. Sheet Chuyên gia: 3 cột
    df_experts = pd.DataFrame([
        {"Expert_Name": "GS. Nguyen Van A", "Username": "expert01", "Password": "123"},
        {"Expert_Name": "TS. Tran Thi B", "Username": "expert02", "Password": "123"},
        {"Expert_Name": "ThS. Le Van C", "Username": "expert03", "Password": "123"}
    ])

    # Ghi ra file Excel
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_factors.to_excel(writer, sheet_name="Factors_Alternatives", index=False)
        df_scale_standard.to_excel(writer, sheet_name="Scale_Standard", index=False)
        df_scale_z_number.to_excel(writer, sheet_name="Scale_Z_Number", index=False)
        df_experts.to_excel(writer, sheet_name="Experts", index=False)
        
    print(f"[OK] Đã tạo template mẫu thành công tại: {output_path}")

from core.models import ProjectConfig, Factor, ScaleItem, Expert

def parse_config_excel(file_path: str, config: ProjectConfig) -> ProjectConfig:
    """Đọc file Excel và nạp dữ liệu vào đối tượng ProjectConfig."""
    xls = pd.ExcelFile(file_path)
    config.excel_path = file_path
    
    # 1. Đọc sheet Factors_Alternatives
    if "Factors_Alternatives" in xls.sheet_names:
        df_fa = pd.read_excel(xls, "Factors_Alternatives").fillna("")
        config.factors = []
        config.alternatives = []
        for _, row in df_fa.iterrows():
            item_type = str(row.get("Type", "Factor")).strip()
            item = Factor(
                type=item_type,
                code=str(row.get("Code", "")).strip(),
                name=str(row.get("Name", "")).strip(),
                description=str(row.get("Description", "")).strip()
            )
            if item_type.lower() == "alternative":
                config.alternatives.append(item)
            else:
                config.factors.append(item)

    # 2. Đọc Sheet thang đo
    if config.scale_type == "Category":
        if not config.use_z_number:
            # Thang đo thông thường (3 cột)
            sheet_name = "Scale_Standard" if "Scale_Standard" in xls.sheet_names else xls.sheet_names[1]
            df_scale = pd.read_excel(xls, sheet_name).fillna("")
            config.standard_scales = []
            for _, row in df_scale.iterrows():
                config.standard_scales.append(ScaleItem(
                    linguistic=str(row.iloc[0]).strip(),
                    code=str(row.iloc[1]).strip(),
                    value=row.iloc[2]
                ))
        else:
            # Thang đo Z-number (6 cột)
            sheet_name = "Scale_Z_Number" if "Scale_Z_Number" in xls.sheet_names else xls.sheet_names[1]
            df_z = pd.read_excel(xls, sheet_name).fillna("")
            config.z_scales_a = []
            config.z_scales_b = []
            for _, row in df_z.iterrows():
                # 3 cột đầu: A
                config.z_scales_a.append(ScaleItem(
                    linguistic=str(row.iloc[0]).strip(),
                    code=str(row.iloc[1]).strip(),
                    value=row.iloc[2]
                ))
                # 3 cột sau: B (nếu có đủ 6 cột)
                if len(row) >= 6:
                    config.z_scales_b.append(ScaleItem(
                        linguistic=str(row.iloc[3]).strip(),
                        code=str(row.iloc[4]).strip(),
                        value=row.iloc[5]
                    ))

    # 3. Đọc Sheet Experts (nếu chế độ Account)
    if config.expert_auth_mode == "Account" and "Experts" in xls.sheet_names:
        df_exp = pd.read_excel(xls, "Experts").fillna("")
        config.experts = []
        for _, row in df_exp.iterrows():
            config.experts.append(Expert(
                name=str(row.iloc[0]).strip(),
                username=str(row.iloc[1]).strip(),
                password=str(row.iloc[2]).strip()
            ))

    return config

def export_all_experts_results(file_code_path: str, file_value_path: str,
                               config: ProjectConfig,
                               all_experts_data: dict,
                               row_labels: list, col_labels: list):
    """Export responses using stable Ans_XX sheet names.

    Expert names are metadata only and may repeat. Each workbook therefore has
    a Lookup sheet mapping Ans_01, Ans_02, ... to respondent/expert/source data.
    """

    def build_lookup():
        rows = []
        for idx, (key, data) in enumerate(all_experts_data.items(), start=1):
            rows.append({
                "Answer_ID": data.get("answer_id") or f"Ans_{idx:02d}",
                "Respondent_ID": data.get("respondent_id", key),
                "Expert_Name": data.get("expert_name", ""),
                "Username": data.get("username", ""),
                "Source_Project_ID": data.get("source_project_id", ""),
                "Source_Project": data.get("source_project_name", ""),
                "Submitted_At": data.get("submitted_at", ""),
            })
        return pd.DataFrame(rows)

    meta_list = [
        {"Parameter": "Model_Type", "Value": config.model_type},
        {"Parameter": "Use_Z_Number", "Value": "YES" if config.use_z_number else "NO"},
        {"Parameter": "Scale_Type", "Value": config.scale_type},
        {"Parameter": "Total_Experts_Saved", "Value": len(all_experts_data)},
    ]

    def write_workbook(path, value_key):
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame(meta_list).to_excel(writer, sheet_name="Metadata", index=False)
            build_lookup().to_excel(writer, sheet_name="Lookup", index=False)

            # Deterministic ordering by answer number where available.
            items = list(all_experts_data.items())
            items.sort(key=lambda item: item[1].get("answer_id", item[0]))
            for idx, (key, data) in enumerate(items, start=1):
                answer_id = data.get("answer_id") or f"Ans_{idx:02d}"
                answer_id = str(answer_id)[:31]
                matrix = data.get(value_key, [])
                df = pd.DataFrame(matrix, index=row_labels, columns=col_labels)
                df.to_excel(writer, sheet_name=answer_id)

    write_workbook(file_code_path, "code_matrix")
    write_workbook(file_value_path, "value_matrix")

if __name__ == "__main__":
    generate_default_template()