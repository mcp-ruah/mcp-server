FROM python:3.13-slim
WORKDIR /app

# curl 설치
RUN apt-get update && apt-get install -y curl

# 전체 프로젝트 복사
COPY . .

# uv 설치 (전역 설치 위치로 들어감)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# uv가 설치된 경로를 PATH에 추가
ENV PATH="/root/.local/bin:${PATH}"

# 가상환경 생성 및 프로젝트 설치
RUN uv venv .venv && uv pip install -r pyproject.toml

# 필요한 포트 오픈
EXPOSE 8006

# MCP 서버 실행
ENTRYPOINT ["uv", "run", "mcp", "run", "tools/weather.py:mcp"]