import asyncio
import json
import os
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

# 테스트할 경로 설정
ROOT_FOLDER = r"D:/project/data/차량데이터/임시폴더_파싱구분용(차량)하위폴더"
OUTPUT_IMAGES = ROOT_FOLDER + "_extracted_images"
PREPROCESSED_JSON = ROOT_FOLDER + "_preprocessed.json"
FINAL_JSON = ROOT_FOLDER + "_data.json"
FINAL_CSV = ROOT_FOLDER + "_maintenance_data.csv"
TXT_OUTPUT = os.path.join(ROOT_FOLDER, "descriptions.txt")

async def main():
    # pdf_tools.py 서버 실행 (표준입출력 방식)
    server_params = StdioServerParameters(
        command="python",
        args=["pdf_tools.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) PDF 전처리 테스트
            resp = await session.call_tool("preprocess_pdfs", {
                "root_folder": ROOT_FOLDER,
                "output_images_folder": OUTPUT_IMAGES,
                "preprocessed_json_path": PREPROCESSED_JSON,
                "invert_percentile": 40
            })
            print("[Preprocess]", resp)

            # 전처리 JSON 로드 및 첫 레코드에서 이미지 경로 추출
            with open(PREPROCESSED_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            first_record = data[0]['records'][0]
            prim_path = first_record['primary_image_path']
            full_path = first_record['fullpage_image_path']

            # 2) 중복 제거 테스트
            resp = await session.call_tool("deduplicate_images", {
                "preprocessed_json_path": PREPROCESSED_JSON,
                "image_root_folder": OUTPUT_IMAGES,
                "duplicate_threshold": 2
            })
            print("[Deduplicate]", resp)

            # 3) 주요 이미지 설명 테스트
            resp = await session.call_tool("describe_primary_image", {
                "primary_image_path": prim_path,
                "fullpage_image_path": full_path
            })
            print("[Primary Image Description]", resp)

            # 4) 전체 페이지 Q&A 테스트
            resp = await session.call_tool("describe_fullpage_image", {
                "fullpage_image_path": full_path
            })
            print("[Fullpage Q&A]", resp)

            # 5) 전체 파이프라인 증분 처리 테스트
            resp = await session.call_tool("generate_incremental_data", {
                "preprocessed_json_path": PREPROCESSED_JSON,
                "final_json_path": FINAL_JSON,
                "final_csv_path": FINAL_CSV,
                "txt_output_path": TXT_OUTPUT
            })
            print("[Pipeline]", resp)

if __name__ == "__main__":
    asyncio.run(main())