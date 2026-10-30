import sys
from pathlib import Path

# 프로젝트 루트(tf 패키지가 있는 곳)를 import 경로에 넣는다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
