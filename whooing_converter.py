import pandas as pd
import os
from typing import List, Dict, Any

def convert_to_whooing_excel(whooing_rows: List[Dict[str, Any]], template_path: str, output_path: str):
    """
    Converts Whooing rows (List[Dict]) into the Excel format required by whooing_default.xlsx.
    Whooing rows format: {'날짜': '2026-01-30', '아이템': 'Coffee', '금액': 5000, '왼쪽': '식비', '오른쪽': '현금', '메모': 'memo', '시간': 'HH:MM:SS'}
    Target Columns in Template: 날짜, 아이템(괄호), 금액, 왼쪽, 오른쪽, 메모
    """
    if not whooing_rows:
        print("No rows to convert to Excel.")
        return

    # Load template
    try:
        df_template = pd.read_excel(template_path)
    except Exception as e:
        print(f"Error loading template {template_path}: {e}")
        # Create a fresh dataframe if template fails
        df_template = pd.DataFrame(columns=["날짜", "아이템(괄호)", "금액", "왼쪽", "오른쪽", "메모"])

    # Prepare data for output
    data = []
    for row in whooing_rows:
        data.append({
            "날짜": row.get("날짜"),
            "아이템(괄호)": row.get("아이템"),
            "금액": row.get("금액"),
            "왼쪽": row.get("왼쪽"),
            "오른쪽": row.get("오른쪽"),
            "메모": row.get("메모")
        })

    df_out = pd.DataFrame(data)

    # Use openpyxl to write to the template or just save it
    # Since we want to preserve header styling (if any) we could use an existing engine
    # But for simplicity, we can just save it.
    try:
        df_out.to_excel(output_path, index=False)
        print(f"Successfully saved Whooing upload file to {output_path}")
    except Exception as e:
        print(f"Error saving Excel file: {e}")

if __name__ == "__main__":
    # Test logic if needed
    pass
