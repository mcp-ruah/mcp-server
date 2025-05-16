from mcp.server.fastmcp import FastMCP
from pathlib import Path
import fitz            # PyMuPDF
from PIL import Image, ImageOps  # pip install pillow
import os, io, json, hashlib, base64
from collections import defaultdict
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
import sys

# 환경 변수 로드 & OpenAI 클라이언트 초기화
load_dotenv()
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print(f"OpenAI 클라이언트 초기화 오류: {e}")
    sys.exit(1)

# MCP 서버 인스턴스 생성
mcp = FastMCP("pdf_data")

def maybe_correct_inversion(image: Image.Image, invert_percentile: float = 40) -> Image.Image:
    """
    이미지 밝기 분포의 invert_percentile 백분위가 128 미만이면 반전합니다.
    """

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    gray = image.convert("L")
    vals = np.array(gray).flatten()
    if np.percentile(vals, invert_percentile) < 128:
        return ImageOps.invert(image)
    return image


def extract_primary_and_fullpage_images_from_pdf(
    pdf_path: str,
    output_folder: str,
    invert_percentile: float = 40
) -> list:
    """
    PDF의 각 페이지에서 primary 및 fullpage 이미지를 추출하고 메타 정보를 반환합니다.
    """
    os.makedirs(output_folder, exist_ok=True)
    doc = fitz.open(pdf_path)
    records = []
    base_name = Path(pdf_path).stem.strip()

    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)
        if not images:
            continue

        # fullpage 이미지 (2배 해상도)
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        full_name = f"{base_name}_p{page_index+1}_full.png"
        full_path = os.path.join(output_folder, full_name)
        pix.save(full_path)

        # 각 primary 이미지
        for img_index, img in enumerate(images):
            xref = img[0]
            img_data = doc.extract_image(xref)
            img_bytes = img_data["image"]
            img_obj = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            img_obj = maybe_correct_inversion(img_obj, invert_percentile)

            prim_name = f"{base_name}_p{page_index+1}_primary_{img_index+1}.png"
            prim_path = os.path.join(output_folder, prim_name)
            img_obj.save(prim_path, format="PNG")

            records.append({
                "primary_image_path": prim_path,
                "fullpage_image_path": full_path,
                "page_index": page_index,
                "image_index": img_index
            })

    return records


@mcp.tool(
    name="preprocess_pdfs",
    description="폴더 내 PDF에서 이미지 추출 후 preprocessed JSON으로 저장"
)
def preprocess_pdfs(
    root_folder: str,
    output_images_folder: str,
    preprocessed_json_path: str,
    invert_percentile: float = 40
) -> str:
    """
    주어진 폴더(root_folder) 내 모든 PDF를 탐색해
    이미지 추출 후 preprocessed_json_path에 저장합니다.
    """
    data = []
    processed = set()
    try:
        if os.path.exists(preprocessed_json_path):
            try:
                with open(preprocessed_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    processed = {e["pdf_path"] for e in data}
            except json.JSONDecodeError:
                data = []

        for dirpath, _, filenames in os.walk(root_folder):
            # 상대 경로 파트를 얻어 각 부분 strip 처리
            rel = os.path.relpath(dirpath, root_folder)
            safe_parts = [part.strip() for part in rel.split(os.sep) if part.strip()]
            safe_rel = os.path.join(*safe_parts) if safe_parts else ""

            for fn in filenames:
                if not fn.lower().endswith(".pdf"):
                    continue
                pdf_path = os.path.join(dirpath, fn)
                if pdf_path in processed:
                    continue

                # 출력 디렉토리 경로
                out_dir = os.path.join(
                    output_images_folder, safe_rel, Path(fn).stem.strip()
                )
                recs = extract_primary_and_fullpage_images_from_pdf(
                    pdf_path, out_dir, invert_percentile
                )
                data.append(
                    {
                        "pdf_path": pdf_path,
                        "pdf_base": Path(fn).stem.strip(),
                        "records": recs,
                    }
                )

        with open(preprocessed_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return f"전처리 완료: {preprocessed_json_path}"
    except Exception as e:
        error_msg = f"오류 발생: {str(e)}"
        print(error_msg)  # 서버 로그에 출력
        return error_msg  # 클라이언트에 전달


def compute_file_hash(file_path: str, hash_algo: str = 'md5') -> str:
    """파일의 해시를 계산합니다."""
    h = hashlib.new(hash_algo)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            h.update(chunk)
    return h.hexdigest()


@mcp.tool(
    name="deduplicate_images",
    description="해시값 기준 중복 primary 이미지 삭제 및 JSON 갱신"
)
def deduplicate_images(
    preprocessed_json_path: str,
    image_root_folder: str,
    duplicate_threshold: int = 2
) -> str:
    """
    preprocessed JSON 로드 후,
    동일 해시값 이미지가 threshold 이상인 경우 중복 제거
    """
    with open(preprocessed_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    dup = defaultdict(lambda: defaultdict(list))
    for root, _, files in os.walk(image_root_folder):
        for fn in files:
            if fn.lower().endswith('.png') and '_primary_' in fn:
                fp = os.path.join(root, fn)
                top = os.path.relpath(fp, image_root_folder).split(os.sep)[0]
                h = compute_file_hash(fp)
                dup[top][h].append(fp)

    to_remove = set()
    for grp in dup.values():
        for h, paths in grp.items():
            if len(paths) >= duplicate_threshold:
                paths.sort()
                to_remove.update(paths[1:])

    new_data = []
    for e in data:
        new_recs = [r for r in e['records'] if r['primary_image_path'] not in to_remove]
        if new_recs:
            e['records'] = new_recs
            new_data.append(e)
    data = new_data

    for fp in to_remove:
        try:
            os.remove(fp)
        except:
            pass

    with open(preprocessed_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return f"중복 제거 완료: {preprocessed_json_path}"


@mcp.tool(
    name="describe_primary_image",
    description="primary+fullpage 이미지로 GPT 설명 생성"
)
def describe_primary_image(
    primary_image_path: str,
    fullpage_image_path: str
) -> str:
    def encode(path):
        b = open(path, 'rb').read()
        return f"data:image/png;base64,{base64.b64encode(b).decode()}"

    p_img = encode(primary_image_path)
    f_img = encode(fullpage_image_path)
    prompt = (
        "아래 두 이미지를 참고하세요. 첫 번째는 핵심 이미지, 두 번째는 전체 페이지입니다."
        " 첫 번째 이미지에 대한 상세 설명을 작성해 주세요."
    )
    try:
        res = client.responses.create(
            model="gpt-4o",
            input=[
                {"role":"user","content":prompt},
                {"role":"user","content":[
                    {"type":"input_image","image_url":p_img},
                    {"type":"input_image","image_url":f_img}
                ]}
            ]
        )
        return res.output_text.strip()
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool(
    name="describe_fullpage_image",
    description="fullpage 이미지로 한국어 Q&A 학습 데이터 생성"
)
def describe_fullpage_image(fullpage_image_path: str) -> str:
    b = open(fullpage_image_path, 'rb').read()
    img = f"data:image/png;base64,{base64.b64encode(b).decode()}"
    prompt = (
        "다음 이미지는 정비 매뉴얼 페이지입니다."
        " '단어|(학습용)질문|(답변)' 형식으로 10~20개 생성해 주세요."
    )
    try:
        res = client.responses.create(
            model="gpt-4o",
            input=[
                {"role":"user","content":prompt},
                {"role":"user","content":[{"type":"input_image","image_url":img}]}]
        )
        return res.output_text.strip()
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool(
    name="generate_incremental_data",
    description="모든 단계 실행 후 결과를 JSON/CSV/TXT에 증분 저장"
)
def generate_incremental_data(
    preprocessed_json_path: str,
    final_json_path: str,
    final_csv_path: str,
    txt_output_path: str
) -> str:
    os.makedirs(os.path.dirname(txt_output_path), exist_ok=True)
    open(txt_output_path, 'w', encoding='utf-8').close()

    with open(preprocessed_json_path,'r',encoding='utf-8') as f:
        pre = json.load(f)
    processed = set()
    final_json = []
    if os.path.exists(final_json_path):
        try:
            final_json = json.load(open(final_json_path,'r',encoding='utf-8'))
            processed = {r['sample_note'] for r in final_json}
        except:
            pass

    import csv
    final_csv = []
    if os.path.exists(final_csv_path):
        reader = csv.DictReader(open(final_csv_path,'r',encoding='utf-8-sig'))
        final_csv = list(reader)

    for entry in pre:
        pdf = entry['pdf_path']
        if pdf in processed:
            continue
        base = entry['pdf_base']
        # 기본 질문 설정
        q_prim = f"위 {base} 이미지 설명해 주세요."
        q_full = f"위 {base} 전체 페이지 요약해 주세요."
        cnt = 0
        for r in entry['records']:
            p, f = r['primary_image_path'], r['fullpage_image_path']
            if not os.path.exists(p) or not os.path.exists(f):
                continue
            desc = describe_primary_image(p, f)
            open(txt_output_path,'a',encoding='utf-8').write(f"{p} | {desc}\n")
            final_json.append({
                "sample_note":pdf,
                "question":q_prim,
                "model_prediction":desc,
                "figure_id":str(cnt)
            })
            mdata = describe_fullpage_image(f)
            final_csv.append({
                "sample_note":pdf,
                "question":q_full,
                "maintenance_data":mdata,
                "figure_id":str(cnt)
            })
            cnt += 1
        processed.add(pdf)
        with open(final_json_path,'w',encoding='utf-8') as jf:
            json.dump(final_json, jf, ensure_ascii=False, indent=2)
        if final_csv:
            keys = final_csv[0].keys()
            with open(final_csv_path,'w',newline='',encoding='utf-8-sig') as cf:
                w = csv.DictWriter(cf, fieldnames=keys)
                w.writeheader()
                w.writerows(final_csv)

    return f"증분 처리 완료: {final_json_path}, {final_csv_path}, {txt_output_path}"

if __name__ == "__main__":

    print("Starting MCP server...")
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        print(f"MCP 서버 실행 중 오류 발생: {e}")
        sys.exit(1)
