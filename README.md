## quick start

```
uv init --python 3.13 // 원하는 버전		

uv venv 	// .venv 가상환경 설치

// Window
./.venv/Scripts/activate

// MacOS
source .venv/bin/activate 

// 라이브러리 설치
uv pip install -e .
```


## docker
```
//docker build
docker build -t mcp/weather .

// docker execution(mcp서버가 알아서 실행하기때문에 안해도됨)
docker run -p 8006:8006 -i --rm mcp/weather
```

