# ECOS Economic Data MCP Server

한국은행 ECOS Open API를 자연어 지표 검색, 정규화된 시계열 조회, 비교와 객관적 통계 계산으로 제공하는 공유형 MCP 서버입니다. 경제적 해석이나 투자 판단은 반환하지 않습니다. 현재 `FastMCP` 기반 구현과 호환되는 공식 MCP Python SDK v1 유지보수 라인(`mcp<2`)을 사용합니다.

## Architecture

`MCP tool -> service -> EcosClient -> ECOS Open API` 구조이며, MCP 등록부와 데이터 계층을 분리했습니다. `DataProvider`를 추가할 수 있도록 ECOS client를 독립 경계로 두었고, SQLite 캐시는 동일 요청을 공유합니다. 모든 응답에는 출처, 코드, 단위, 주기, 조회 시각이 포함됩니다.

## Setup

ECOS에서 API 인증키를 발급한 뒤 `.env.example`을 `.env`로 복사하고 `ECOS_API_KEY`를 입력합니다. 키는 소스와 로그에 기록하지 않습니다.

```powershell
uv sync --extra dev
uv run pytest
uv run ecos-mcp
```

기본 endpoint는 `http://localhost:18765/mcp`입니다. `MCP_HOST`, `MCP_PORT`, timeout, retry, cache TTL은 환경변수로 바꿀 수 있습니다.

## Docker

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

NanoClaw가 같은 Compose 네트워크에 있으면 `http://ecos-mcp:18765/mcp`, 호스트에서 실행하면 `http://localhost:18765/mcp`를 사용합니다. MCP Inspector는 `npx @modelcontextprotocol/inspector http://localhost:18765/mcp`로 연결한 뒤 tools 목록과 `search_statistics`, `get_latest_value`, `get_statistics`, `compare_statistics`, `calculate_change`, `calculate_spread`, `calculate_correlation`을 호출합니다.

## Tools

`search_statistics`는 통계표/항목 후보와 점수를 반환하며 동률 후보를 임의 선택하지 않습니다. `get_statistics`와 `get_latest_value`는 자연어 지표를 실제 ECOS 코드로 해석해 정규화합니다. `compare_statistics`는 공통 기간만 정렬하고 각 시리즈 단위를 보존합니다. `calculate_change`는 절대 변화, 변화율, MoM, QoQ, YoY를 지원합니다. `calculate_spread`는 단위가 같은 두 시리즈만 결합합니다. `calculate_correlation`은 공통 기간의 Pearson 상관계수와 표본 수를 반환하며 인과관계를 주장하지 않습니다. `calculate_statistics`는 평균, 중앙값, 최솟값, 최댓값, 표준편차, 분산을 계산합니다. `get_economic_snapshot`은 실제로 검색/조회되는 한국 지표만 포함하고 없는 지표는 unavailable로 표시합니다.

예시 요청은 `한국 기준금리`, `소비자물가`, `원달러 환율`, `M2`, `GDP 성장률`처럼 자연어로 입력합니다. 미국 지표는 ECOS에 실제 존재하고 검색되는 경우에만 반환됩니다.

## Limitations and next provider

ECOS 메타데이터의 표기 차이와 API 제공 범위 때문에 일부 자연어 질의는 후보 선택이 필요할 수 있습니다. 일별 자료를 월별로 자동 집계하는 변환은 아직 보수적으로 지원하지 않으며, 비교 요청의 frequency를 명시해야 합니다. API 통합 테스트는 키가 필요하므로 기본 테스트는 mock입니다.

향후 FRED를 추가할 때 `EcosClient`와 동일한 `DataProvider` 인터페이스를 정의하고 `FredProvider`를 구현한 다음, 지표 해석 결과에 `provider`를 포함시키면 됩니다. provider가 다른 자료의 결합은 단위, 주기, 기간, 출처 검증을 통과한 경우에만 허용해야 합니다.
