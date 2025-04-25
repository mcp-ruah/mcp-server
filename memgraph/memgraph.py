from mcp.server.fastmcp import FastMCP
import os
import platform
from dotenv import load_dotenv
from neo4j import GraphDatabase
import sys

# 환경 변수 로드 시도
load_dotenv()


# Memgraph 연결 설정 (Neo4j 드라이버 사용)
def get_connection_settings():
    """환경 변수에서 연결 설정을 가져옵니다."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    # 바이트 문자열 변환 처리
    if isinstance(uri, bytes):
        uri = uri.decode("utf-8")
    if isinstance(username, bytes):
        username = username.decode("utf-8")
    if isinstance(password, bytes):
        password = password.decode("utf-8")

    # 환경 변수 로깅
    print(f"연결 URI: {uri}")
    print(f"사용자명: {username}")
    print(f"비밀번호: {'*' * len(password) if password else None}")

    return uri, username, password


# 연결 설정 가져오기
NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD = get_connection_settings()

# MCP 서버 생성
mcp = FastMCP("memgraph_cypher")


# Neo4j 드라이버를 이용한 Memgraph 데이터베이스 연결 함수
def get_neo4j_driver():
    """Neo4j 드라이버를 이용하여 Memgraph 데이터베이스에 연결합니다."""
    try:
        if not NEO4J_URI:
            raise ValueError(
                "NEO4J_URI 환경 변수가 설정되지 않았습니다. "
                "환경 변수를 설정하거나 Docker 실행 시 -e 옵션을 사용하세요."
            )

        # 인증 정보가 비어있으면 인증 없이 연결
        if NEO4J_USERNAME and NEO4J_PASSWORD:
            driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
            )
        else:
            driver = GraphDatabase.driver(NEO4J_URI)

        # 연결 테스트
        with driver.session() as session:
            session.run("RETURN 1")
            print("데이터베이스 연결 성공!")

        return driver
    except Exception as e:
        error_msg = f"Memgraph 연결 실패: {str(e)}"
        print(f"오류: {error_msg}")
        print(f"현재 연결 URI: {NEO4J_URI}")
        print("Docker 환경에서 실행 중이라면 다음을 확인하세요:")
        print("1. 환경 변수가 올바르게 설정되었는지 (-e 옵션)")
        print("2. 호스트 이름이 올바른지 (localhost 대신 host.docker.internal)")
        print("3. 데이터베이스가 실행 중인지")
        raise RuntimeError(error_msg)


# Tool 1: Cypher 쿼리 실행
@mcp.tool(
    name="execute_cypher_query",
    description="Memgraph 데이터베이스에서 Cypher 쿼리를 실행합니다.",
)
def execute_cypher_query(query: str) -> list:
    """Memgraph 데이터베이스에서 Cypher 쿼리를 실행하고 결과를 반환합니다."""
    try:
        driver = get_neo4j_driver()

        results = []
        with driver.session() as session:
            result = session.run(query)
            # 결과를 딕셔너리 리스트로 변환
            for record in result:
                results.append(dict(record))

        return results
    except Exception as e:
        raise RuntimeError(f"쿼리 실행 실패: {str(e)}")
    finally:
        if "driver" in locals():
            driver.close()


# Tool 2: 스키마 정보 조회
@mcp.tool(
    name="get_schema_info",
    description="Memgraph 데이터베이스의 스키마 정보(노드 레이블, 관계 타입, 속성)를 조회합니다.",
)
def get_schema_info() -> dict:
    """Memgraph 데이터베이스의 스키마 정보를 반환합니다."""
    try:
        driver = get_neo4j_driver()

        node_labels = set()
        rel_types = set()
        properties = set()

        with driver.session() as session:
            # 노드 레이블 조회
            labels_result = session.run("MATCH (n) RETURN DISTINCT labels(n) as labels")
            for record in labels_result:
                for label in record["labels"]:
                    node_labels.add(label)

            # 관계 타입 조회
            rel_result = session.run("MATCH ()-[r]->() RETURN DISTINCT type(r) as type")
            for record in rel_result:
                rel_types.add(record["type"])

            # 속성 조회
            prop_query = """
            MATCH (n)
            UNWIND keys(n) AS property
            RETURN DISTINCT property
            UNION
            MATCH ()-[r]->()
            UNWIND keys(r) AS property
            RETURN DISTINCT property
            """
            prop_result = session.run(prop_query)
            for record in prop_result:
                properties.add(record["property"])

        return {
            "node_labels": list(node_labels),
            "relationship_types": list(rel_types),
            "properties": list(properties),
        }
    except Exception as e:
        raise RuntimeError(f"스키마 정보 조회 실패: {str(e)}")
    finally:
        if "driver" in locals():
            driver.close()


# Tool 3: 데이터베이스 통계
@mcp.tool(
    name="get_database_stats",
    description="Memgraph 데이터베이스의 통계 정보를 조회합니다.",
)
def get_database_stats() -> dict:
    """Memgraph 데이터베이스의 통계 정보를 반환합니다."""
    try:
        driver = get_neo4j_driver()

        with driver.session() as session:
            # 노드 수 조회
            nodes_result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = nodes_result.single()["node_count"]

            # 관계 수 조회
            rels_result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
            rel_count = rels_result.single()["rel_count"]

            # 레이블별 노드 수 조회
            labels_query = """
            MATCH (n)
            WITH labels(n) as labels
            UNWIND labels as label
            RETURN label, count(*) as count
            """
            labels_result = session.run(labels_query)
            label_counts = {}
            for record in labels_result:
                label_counts[record["label"]] = record["count"]

            # 타입별 관계 수 조회
            rels_type_query = """
            MATCH ()-[r]->()
            RETURN type(r) as type, count(*) as count
            """
            rels_type_result = session.run(rels_type_query)
            rel_type_counts = {}
            for record in rels_type_result:
                rel_type_counts[record["type"]] = record["count"]

        return {
            "node_count": node_count,
            "relationship_count": rel_count,
            "node_counts_by_label": label_counts,
            "relationship_counts_by_type": rel_type_counts,
        }
    except Exception as e:
        raise RuntimeError(f"데이터베이스 통계 조회 실패: {str(e)}")
    finally:
        if "driver" in locals():
            driver.close()


# Tool 4: 그래프 생성 및 수정
@mcp.tool(
    name="modify_graph",
    description="CREATE, MERGE, DELETE 등의 Cypher 쿼리를 사용하여 그래프를 수정합니다.",
)
def modify_graph(query: str) -> dict:
    """Memgraph 데이터베이스의 그래프 구조를 수정하고 결과를 반환합니다."""
    try:
        driver = get_neo4j_driver()

        # 쿼리가 변경 작업인지 확인 (CREATE, MERGE, DELETE, SET 등으로 시작하는지)
        modify_keywords = ["CREATE", "MERGE", "DELETE", "SET", "REMOVE"]
        is_modify_query = any(
            query.strip().upper().startswith(keyword) for keyword in modify_keywords
        )

        if not is_modify_query:
            raise ValueError(
                "이 도구는 그래프 수정 쿼리(CREATE, MERGE, DELETE 등)에만 사용할 수 있습니다."
            )

        # 수정 쿼리 실행
        with driver.session() as session:
            result = session.run(query)
            summary = result.consume()

            # 영향받은 노드 및 관계 개수 계산
            nodes_created = summary.counters.nodes_created
            nodes_deleted = summary.counters.nodes_deleted
            relationships_created = summary.counters.relationships_created
            relationships_deleted = summary.counters.relationships_deleted
            properties_set = summary.counters.properties_set

            affected_items = (
                nodes_created
                + nodes_deleted
                + relationships_created
                + relationships_deleted
                + properties_set
            )

        return {
            "status": "success",
            "message": "그래프가 성공적으로 수정되었습니다.",
            "summary": {
                "nodes_created": nodes_created,
                "nodes_deleted": nodes_deleted,
                "relationships_created": relationships_created,
                "relationships_deleted": relationships_deleted,
                "properties_set": properties_set,
            },
            "affected_items": affected_items,
        }
    except Exception as e:
        raise RuntimeError(f"그래프 수정 실패: {str(e)}")
    finally:
        if "driver" in locals():
            driver.close()


# Tool 5: 여러 Cypher 쿼리 실행
@mcp.tool(
    name="execute_multiple_queries",
    description="여러 Cypher 쿼리를 순차적으로 실행합니다.",
)
def execute_multiple_queries(queries: list) -> dict:
    """여러 Cypher 쿼리를 순차적으로 실행하고 결과를 반환합니다."""
    try:
        driver = get_neo4j_driver()

        results = []
        with driver.session() as session:
            for idx, query in enumerate(queries):
                try:
                    result = session.run(query)
                    # 읽기 쿼리인 경우 결과를 저장
                    if query.strip().upper().startswith(
                        "MATCH"
                    ) or query.strip().upper().startswith("RETURN"):
                        query_results = []
                        for record in result:
                            query_results.append(dict(record))
                        results.append(
                            {
                                "query_index": idx,
                                "query": query,
                                "status": "success",
                                "results": query_results,
                            }
                        )
                    else:
                        # 쓰기 쿼리인 경우 영향받은 항목 개수 저장
                        summary = result.consume()
                        results.append(
                            {
                                "query_index": idx,
                                "query": query,
                                "status": "success",
                                "affected_items": (
                                    summary.counters.nodes_created
                                    + summary.counters.nodes_deleted
                                    + summary.counters.relationships_created
                                    + summary.counters.relationships_deleted
                                    + summary.counters.properties_set
                                ),
                            }
                        )
                except Exception as e:
                    results.append(
                        {
                            "query_index": idx,
                            "query": query,
                            "status": "error",
                            "error": str(e),
                        }
                    )

        return {
            "total_queries": len(queries),
            "successful_queries": sum(1 for r in results if r["status"] == "success"),
            "failed_queries": sum(1 for r in results if r["status"] == "error"),
            "results": results,
        }
    except Exception as e:
        raise RuntimeError(f"쿼리 실행 실패: {str(e)}")
    finally:
        if "driver" in locals():
            driver.close()


# 서버 실행
if __name__ == "__main__":
    print("Starting Memgraph MCP server with Neo4j driver...")
    mcp.run(transport="stdio")
