# Memgraph MCP 서버

이 MCP 서버는 Memgraph 데이터베이스에 Cypher 쿼리를 실행할 수 있는 도구를 제공합니다. Neo4j 드라이버를 사용하여 Memgraph와 통신합니다.


memgraph 시각화 


## 기능

이 MCP 서버는 다음과 같은 도구를 제공합니다:

1. **execute_cypher_query**: Memgraph 데이터베이스에서 단일 Cypher 쿼리를 실행합니다.
2. **get_schema_info**: 데이터베이스의 스키마 정보(노드 레이블, 관계 타입, 속성)를 조회합니다.
3. **get_database_stats**: 데이터베이스의 통계 정보(노드 수, 관계 수 등)를 조회합니다.
4. **modify_graph**: CREATE, MERGE, DELETE 등의 Cypher 쿼리를 사용하여 그래프를 수정합니다.
5. **execute_multiple_queries**: 여러 Cypher 쿼리를 순차적으로 실행합니다.

## 설정

환경 변수를 사용하여 Memgraph 데이터베이스 연결 정보를 설정할 수 있습니다:

- `NEO4J_URI`: Memgraph 데이터베이스의 URI (기본값: "bolt://localhost:7687")
- `NEO4J_USERNAME`: 데이터베이스 인증 사용자 이름 (기본값: "")
- `NEO4J_PASSWORD`: 데이터베이스 인증 비밀번호 (기본값: "")

## 사용 예시

### Cypher 쿼리 실행

```python
# Cypher 쿼리 실행
result = await call_tool("execute_cypher_query", {
    "query": "MATCH (n) RETURN n LIMIT 10"
})
```

### 스키마 정보 조회

```python
# 스키마 정보 조회
schema_info = await call_tool("get_schema_info", {})
```

### 데이터베이스 통계 조회

```python
# 데이터베이스 통계 조회
stats = await call_tool("get_database_stats", {})
```

### 그래프 수정

```python
# 노드 생성
create_result = await call_tool("modify_graph", {
    "query": "CREATE (n:Person {name: '홍길동', age: 30}) RETURN n"
})

# 관계 생성
relation_result = await call_tool("modify_graph", {
    "query": "MATCH (a:Person), (b:Person) WHERE a.name = '홍길동' AND b.name = '김철수' CREATE (a)-[r:KNOWS]->(b) RETURN r"
})
```

### 여러 쿼리 실행

```python
# 여러 쿼리 실행
multiple_results = await call_tool("execute_multiple_queries", {
    "queries": [
        "MATCH (n) DETACH DELETE n",
        "CREATE (n:Person {name: '홍길동', age: 30})",
        "CREATE (n:Person {name: '김철수', age: 25})",
        "MATCH (a:Person), (b:Person) WHERE a.name = '홍길동' AND b.name = '김철수' CREATE (a)-[r:KNOWS]->(b)",
        "MATCH (n)-[r]->(m) RETURN n, r, m"
    ]
})
```

## 설치 및 실행

```bash
# 종속성 설치
pip install -r pyproject.toml
pip install neo4j>=5.15.0

# 서버 실행
mcp run memgraph/memgraph.py:mcp
```

## Docker 실행

```bash
# Docker 이미지 빌드
docker build -t memgraph-mcp -f memgraph/Dockerfile .

# Docker 컨테이너 실행
docker run -p 8008:8008 -e NEO4J_URI="bolt://host.docker.internal:7687" memgraph-mcp
```

## 참고사항

- Memgraph는 Neo4j와 Cypher 쿼리 언어 호환성이 있어 Neo4j 드라이버를 사용하여 연결할 수 있습니다.
- 쿼리 실행 시 오류가 발생하면 적절한 오류 메시지가 반환됩니다.
- Memgraph와 호환되는 Cypher 문법을 사용해야 합니다. 