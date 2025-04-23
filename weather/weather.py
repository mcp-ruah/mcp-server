from typing import Any
import httpx, sys
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP(
    "Weather_server",  # Name of MCP Server
    # instructions="You are a weather assistant that can answer questions about the weather in a given location",
    # host="0.0.0.0",  # host address(0.0.0.0 allows connections form any IP)
    # port=8006,  # Port number for the server
)

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"


# Helper Functions
## National Weather Service API의 데이터를 쿼리하고 서식하기 위해 도우미 기능을 추가
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'unknown')}
Area: {props.get('areaDesc', 'unknown')}
Severity(심각성): {props.get('severity', 'unknown')}
Description: {props.get('description', 'unknown')}
Instructions: {props.get('instruction', 'unknown')}
"""


# Implementing tool execution
@mcp.tool(name="get_alerts", description="Get weather alerts for a US state.")
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state(str): Two-letter state code(e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/activate/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n===\n".join(alerts)


@mcp.tool(name="get_forecast", description="Get weather forecast for a location")
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location

    Args:
        latitude(float): Latitude of the location
        longitude(float): Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:
        forecast = f"""
{period["name"]}
Temperature : {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n===\n".join(forecasts)


if __name__ == "__main__":

    print("Starting MCP server...")
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        print(f"MCP 서버 실행 중 오류 발생: {e}")
        sys.exit(1)
