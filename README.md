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
docker image build -t (도커이미지이름) -f (폴더명)/Dockerfile .

// docker execution(mcp서버가 알아서 실행하기때문에 안해도됨)
docker run -p 8006:8006 -i --rm mcp/weather
```



### exit docker container 
```
// 실행중인 컨테이너 확인
docker ps
```

```
// 출력
CONTAINER ID   IMAGE          COMMAND                   CREATED         STATUS         PORTS                    NAMES
6784f3bbb400   5db99b68d643   "uv run mcp run tool…"   9 minutes ago   Up 9 minutes   0.0.0.0:8006->8006/tcp   zen_liskov
```

```
// container id를 이용하거나 이름으로 중지
docker stop 6784f3bbb400
docker stop zen_liskov
```

