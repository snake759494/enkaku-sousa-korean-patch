# 원격수사 ~진실을 향한 23일간~ 한글패치 (v3.12)

PSP 게임 **원격수사 ~真実への23日間~** (Enkaku Sousa, `UCJS10088`) 한국어 번역 패치입니다.

대사 9,626행과 게임 내 이미지·정적 UI를 한국어로 옮겼습니다. v3.12에서는 PSP 실기·Vita Adrenaline에서 발생하던 부팅 직후 오류를 유발하는 스트림 정렬 문제를 보완했습니다.

---

## 패치 방법

### 준비물

| | |
|---|---|
| 원본 ISO | 아래 MD5와 일치하는 일본판 덤프 |
| xdelta | [xdelta3](https://github.com/jmacd/xdelta-gpl/releases) 또는 xdeltaUI |

원본 ISO는 **직접 덤프한 것을 사용**하십시오. 이 저장소는 게임 데이터를 배포하지 않습니다.

### 원본 ISO 확인

패치를 적용하기 전에 반드시 MD5를 확인하십시오. 다르면 패치가 적용되지 않거나 깨진 결과가 나옵니다.

```
파일명   Enkaku Sousa Shinjitsu eno 23nichikan.iso
크기     739,835,904 바이트
MD5      9f9bb5eec3d2c37f184955b591923e1c
```

Windows에서 확인하는 방법:

```
certutil -hashfile "Enkaku Sousa Shinjitsu eno 23nichikan.iso" MD5
```

### 적용

```
xdelta -d -s "Enkaku Sousa Shinjitsu eno 23nichikan.iso" Enkaku_Korean_v3.12.xdelta Enkaku_Korean_v3.12.iso
```

xdeltaUI를 쓰는 경우 **Apply Patch** 탭에서 Patch에 `.xdelta`, Source에 원본 ISO를 지정하십시오.

### 결과 확인

```
파일명   Enkaku_Korean_v3.12.iso
크기     739,835,904 바이트 (원본과 동일)
MD5      4105d3d7d2ec936fb332a9a7c9ce2cbb
SHA-256  c5179cb32bf7698b28d905f21522f9eeaf202157c639b0e0701d98ac55dd1b17
```

크기가 원본과 같은 것이 정상입니다. 이 패치는 파일을 추가하거나 옮기지 않고 기존 데이터를 제자리에서 교체합니다.

### 실행

PPSSPP에서는 ISO를 열어 실행합니다. 실기에서는 커스텀 펌웨어의 ISO 로더(예: ARK/PRO 계열)가 필요하며, 메모리스틱·SD 카드의 `/ISO` 폴더에 결과 ISO를 복사한 뒤 로더에서 선택하십시오. 정품 펌웨어만으로는 수정된 ISO를 실행할 수 없습니다. **PSP-1000/3000 PRO-C와 Vita Adrenaline은 v3.12를 사용하십시오.** v3.12는 게임의 요구 버전 메타데이터를 `5.02`에서 `5.00`으로 낮추고, 확장된 스크립트의 런타임 포인터 정렬도 보정합니다. 5.00보다 낮은 펌웨어에서는 호환되는 CFW로 먼저 업데이트해야 합니다.

---

## 무엇이 번역되었는가

| 항목 | 분량 |
|---|---|
| 대사 | 9,626행 |
| 조사 질문 | 63장 |
| 메뉴·설정·챕터명 | 85장 |
| 날짜 카드 | 22장 |
| 기소 카운트 | 9장 |
| 인물 관계 라벨 | 21장 |
| 장소명 | 11장 |
| 시스템 메시지 | 6장 |
| 조사 화면 정적 라벨 | 24레코드 |
| 시작 면책 문구 | 1장 |
| 선택지·정답 선택 | 178행 검수 |
| 설정 화면·힌트 패널 | 2장 |
| 명함 | 1장 |

### 아직 일본어로 남아 있는 것

- **일부 `0001` 정적 라벨** (`裁判所` 등) — 판독이 확실하지 않은 4bpp 스트립은 덮어쓰지 않았습니다
- **HUD 표시** (`拘束 N일째`, `メニュー`, `次へ`, 요일) — 여러 문자열이 한 텍스처에 조각으로 붙어 있고 조각 경계가 코드의 UV 좌표에 있어, 잘못 고치면 HUD 전체가 깨집니다
- **신문 기사 2장** — 세로쓰기 밀집 텍스트
- **인물 이름표 20여 장**
- **수첩 1장** — 손글씨

---

## 개발 내역

### 포맷 해석

| | |
|---|---|
| 아카이브 | `PSP_GAME/USRDIR/0000` — LZ11 스트림 2개 + SGXD 사운드뱅크 |
| 스트림0 | UI 텍스처 449장 (T8/T4, 32×32 스위즐 타일) |
| 스트림1 | 폰트 175,104바이트 + 스크립트 |
| 폰트 | 16×16 4bpp, 684타일 × 2 = 1,368 글리프 |
| 글리프 인덱스 | `(리드 − 0x88) × 253 + 트레일` |

### 문자표 복원

초기 문자표에 **중복 배정 423슬롯**이 있었습니다. 서로 다른 글리프가 같은 한자로 해석돼 원문 자체가 깨진 상태였습니다.

449장 글리프를 이미지로 렌더링해 육안 대조한 결과 **248슬롯을 정정**했고, 6,754회분의 오독이 사라졌습니다. 이 과정에서 인명 `播磨`(하리마), 지명 `宮上銀座`(미야카미 긴자), 형사 이름 `三浦`(미우라)가 복원됐습니다. `三浦`는 그전까지 `退職`(퇴직)으로 읽히고 있었습니다.

원문 9,626행 중 **1,886행**이 달라졌습니다.

### 대사 확장

한국어는 일본어의 약 140%를 차지합니다. 텍스트를 늘리려면 스크립트 안의 절대 참조를 모두 다시 계산해야 하고, 이것이 이 프로젝트에서 가장 오래 걸린 부분이었습니다.

### 이미지 패치

텍스처 인코더는 디코더의 역함수로 구현하고 **449장 전부에 대해 왕복 무손실**을 확인한 뒤 사용했습니다. 팔레트는 레코드 간 공유되므로 건드리지 않고, 렌더 결과를 기존 팔레트에 최근접 색으로 매핑합니다. 모든 텍스처가 원본과 같은 바이트 수로 인코딩되므로 스트림 레이아웃이 바뀌지 않습니다.

### 실기 호환

아카이브를 다른 LBA로 옮긴 빌드는 실기에서 `C1-2858-3` 오류가 났습니다. v3.12는 원본과 같은 크기의 `0000`·`0001`을 **원래 LBA에 제자리 교체**하고, 실행 파일(`EBOOT.BIN`, `BOOT.BIN`, `UMD_DATA.BIN`)을 일절 수정하지 않습니다. `0000`은 새 LZ11 스트림만 기록하고 스트림 뒤의 미사용 슬롯·패딩·트레일은 원본 바이트를 그대로 보존하도록 재빌드했습니다. 또한 `PARAM.SFO`는 크기와 구조를 유지한 채 `PSP_SYSTEM_VER` 필드의 `5.02`를 `5.00`으로만 변경합니다.

이번 부팅 오류의 원인은 대사를 확장한 뒤 스트림의 일부 섹션 목적지와 포인터 배열 시작 위치가 4바이트 경계에서 벗어난 것이었습니다. MIPS 실기의 `lw`는 비정렬 주소에서 예외를 내지만 PPSSPP에서는 같은 문제가 드러나지 않을 수 있습니다. `build_runtime_refs.py`는 원본에서 정렬되어 있던 헤더 목적지 10곳과 포인터 배열 시작 33곳을 제약으로 삼아 필요한 위치에만 0 패딩을 삽입하고, 전체 33,371개 참조를 같은 오프셋 맵으로 다시 씁니다. v3.12는 43/43 대상 정렬과 10/10 헤더 목적지 검증을 통과했습니다.

또한 v3.8에서 `0001`의 중복 리소스 블록 식별자까지 MD5로 다시 쓴 회귀를 수정했습니다. 원본이 MD5인 47개 블록만 새 내용에 맞춰 갱신하고, `61 0d 0a`로 시작하는 원본 opaque 식별자 12개는 바이트 그대로 보존합니다. `work/verify_hardware_iso.py`가 ISO9660 디렉터리/LBA, 부팅 파일, LZ11 스트림, 식별자 형식을 자동 검증합니다.

---

## 저장소 구성

```
work/            도구 일체 (Python)
font_extract/    문자표, 원문 TSV, 루비 정보
build/           번역문 TSV, 검수 보고서, 매니페스트
ANALYSIS.md      포맷 분석 기록 (한국어)
```

### 주요 도구

| 파일 | 역할 |
|---|---|
| `work/lzss.py` · `work/lz11_compress.py` | LZ11 압축/해제 |
| `work/texpack.py` · `work/texenc.py` | 텍스처 디코드/인코드 |
| `work/font.py` · `work/build_korean_font.py` | 폰트 글리프 |
| `work/build_runtime_refs.py` | 대사 확장 및 참조 재계산 |
| `work/audit_choices.py` | 선택지·정답 선택의 일본어 잔존 및 매핑 감사 |
| `work/patch_container_text.py` | `0001` 조사 화면 정적 라벨 패치 |
| `work/rebuild_0000.py` | 아카이브 재빌드 |
| `work/patch_param_sfo_version.py` | M33용 `PSP_SYSTEM_VER` 메타데이터 패치 |
| `work/patch_iso_inplace.py` | ISO 제자리 패치 |
| `work/verify_hardware_iso.py` | 실기 호환 ISO·아카이브 무결성 검증 |
| `work/verify_runtime_alignment.py` | stream1 런타임 4바이트 정렬 검증 |

### 직접 빌드하기

원본 ISO를 `iso_extract/`로 풀어둔 뒤:

```
python work/build_runtime_refs.py \
    --base build/stream1_ko_retranslated_v2_font.bin \
    --tsv build/translation_ko_v7_final.tsv \
    --slots build/korean_slots_retranslated_v2.json \
    --out build/stream1_ko_v312.bin \
    --report build/runtime_v312_report.json --translation-is-final

python work/rebuild_0000.py --src iso_extract/PSP_GAME/USRDIR/0000 \
    --plain0 build/stream0_v37.bin --plain1 build/stream1_ko_v312.bin \
    --chain 64 --out build/0000_v312

python work/patch_container_text.py --ledger work/container_ko.json \
    --archive 0001 --out build/0001_v39 --chain 64

python work/patch_param_sfo_version.py --src iso_extract/PSP_GAME/PARAM.SFO \
    --out build/PARAM_SFO_v312 --from-version 5.02 --to-version 5.00

python work/patch_iso_inplace.py --iso "원본.iso" --out Enkaku_Korean_v3.12.iso \
    --replace /PSP_GAME/PARAM.SFO build/PARAM_SFO_v312 \
    --replace /PSP_GAME/USRDIR/0000 build/0000_v312 \
    --replace /PSP_GAME/USRDIR/0001 build/0001_v39

python work/verify_runtime_alignment.py \
    --original font_extract/script_stream.bin \
    --patched build/stream1_ko_v312.bin \
    --report build/runtime_v312_report.json

python work/verify_hardware_iso.py --original "원본.iso" \
    --patched Enkaku_Korean_v3.12.iso --system-version 5.00 \
    --runtime-report build/runtime_v312_report.json
```

---

## 알려진 문제

- 일부 대사에 문장 끝 마침표가 빠져 있습니다
- 일부 대사에 띄어쓰기가 소실된 구간이 있습니다
- 초벌 번역의 어색한 표현이 남아 있습니다
- 원문 일부가 아직 미해독 글리프를 포함합니다

번역 품질 개선은 계속 진행 중입니다.

---

## 라이선스

번역문·도구·문서는 자유롭게 사용하실 수 있습니다. 게임 데이터의 권리는 원저작자에게 있으며, 이 저장소는 게임 데이터를 포함하지 않습니다.
