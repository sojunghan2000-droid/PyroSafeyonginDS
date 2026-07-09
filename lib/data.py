"""데이터 레이어 — Supabase 영구 저장.

테이블: equipment / inspection_tasks / deficiencies / notices / malfunctions
(스키마: 프로젝트 루트 supabase_schema.sql, 최초 시드: seed_supabase.py)

모든 접근은 service_role 클라이언트로 수행한다 (RLS 정책 없음 = 외부 차단,
앱은 서버측이므로 안전). 조치 사진은 Storage 버킷 `action-photos`에 저장.

읽기는 st.cache_data(ttl)로 캐시하고, 쓰기 함수가 해당 캐시를 무효화한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import streamlit as st
from supabase import Client, create_client

EquipmentCategory = Literal[
    "소화기", "간이소화장치", "비상경보장치", "가스누설경보기",
    "간이피난유도선", "방화포", "감지기", "발신기", "수신기",
    "확산소화기", "유도등", "스프링클러", "소화전", "기타",
]
QRStatus = Literal["ASSIGNED", "PENDING"]
HealthStatus = Literal["PASS", "FAIL", "DUE"]
TaskStatus = Literal["Scheduled", "In Progress", "Overdue", "Completed"]
InspectionType = Literal["임시소방시설", "피난로 등", "화기취급감독"]
ResolutionStatus = Literal["완료", "불가"]

ACTION_PHOTO_BUCKET = "action-photos"

# 캐시 TTL(초) — 다른 사용자의 변경이 이 시간 안에 화면에 반영된다.
_CACHE_TTL = 15


@dataclass
class Equipment:
    equipment_id: str
    location_id: str
    category: EquipmentCategory
    equipment_name: str
    serial: str
    qr_status: QRStatus
    last_inspection: date | None
    health_status: HealthStatus
    floor: str
    zone: str
    # 도면 좌표 (0~100 정규화 — 도면 width/height 기준 백분율)
    pixel_x: float = 0.0
    pixel_y: float = 0.0
    # 이 장비에 적용 가능한 점검 유형 목록 (점검 일정 등록 시 자동 후보 필터에 사용)
    inspection_types: list[str] = None  # type: ignore[assignment]
    # v1.1: 도면 위 위치 spot 객체 참조 (없으면 None — 기존 데이터)
    spot_id: str | None = None

    def __post_init__(self) -> None:
        if self.inspection_types is None:
            self.inspection_types = []


@dataclass
class Spot:
    """도면 위 장비 후보 위치 (관리자가 정의). v1.1 추가.
    v1.5+: is_temporary — 점검자가 현장에서 임시 등록한 spot.
    관리자가 위치 마스터에서 속성 보완 후 정식 전환(is_temporary=False)."""
    spot_id: str
    floor: str
    room_name: str
    notes: str
    x_pct: float
    y_pct: float
    is_temporary: bool = False


# 점검 회차 등록 시 사용하는 운영 주기 카탈로그 (v1.5+ / v1.6: 일일 점검 추가)
# 시설 종류와는 직교 — 한 회차에 여러 시설이 포함될 수 있음.
TASK_INSPECTION_TYPES = [
    "일일 점검",   # v1.6: 화기작업구간 점검용 — 작업 시작 전/중 수시
    "주간 점검",
    "월간 점검",
    "분기 점검",
    "연간 점검",
]

# 카테고리 → 기본 적용 점검 주기 (시드/신규 등록 시 자동 채움. 관리자가 수정 가능)
INSPECTION_TYPE_CATEGORY_DEFAULTS: dict[str, list[str]] = {
    "소화기": ["월간 점검", "분기 점검"],
    "확산소화기": ["월간 점검", "분기 점검"],
    "간이소화장치": ["월간 점검"],
    "비상경보장치": ["월간 점검"],
    "가스누설경보기": ["월간 점검"],
    "간이피난유도선": ["월간 점검"],
    "방화포": ["월간 점검"],
    "감지기": ["분기 점검"],
    "발신기": ["분기 점검"],
    "수신기": ["분기 점검"],
    "유도등": ["월간 점검"],
    "스프링클러": ["분기 점검"],
    "소화전": ["분기 점검"],
    "기타": [],
}


def default_inspection_types_for(category: str) -> list[str]:
    return list(INSPECTION_TYPE_CATEGORY_DEFAULTS.get(category, []))


# ---------- v1.6: 신규 점검 종류 카탈로그 (별지5 양식 inspection_types) ----------
# 화기작업·가설컨테이너 점검은 기존 3종(임시소방시설/피난로 등/화기취급감독)과 별개.
# 각 점검 종류에 매핑된 "불량 사유" 카탈로그를 가져 multiselect 입력에 사용.

INSPECTION_KIND_FIRE_WORK = "화기작업구간 점검"
INSPECTION_KIND_CONTAINER = "가설컨테이너 사무실 점검"

# 화기작업구간 점검 — 불량 사유 6종
DEFECT_CODES_FIRE_WORK = [
    "방화포 미비치 또는 파손",
    "소화기 부족/충전 부족/고장",
    "화재감시자 부재 또는 불안전한 행동",
    "가연물 정리정돈 미흡",
    "주변 간섭사항 존재",
    "기타",
]

# 가설컨테이너 사무실 점검 — 불량 사유 7종
DEFECT_CODES_CONTAINER = [
    "소화기 비치·점검 불량",
    "환기팬 설치/작동 불량",
    "외부 차단기·시건 상태 불량",
    "감지기 작동 불량",
    "접지 불량",
    "철제쓰레기통 미사용·인화성물질 보관 불량",
    "기타",
]

# 점검 종류 → 불량 사유 카탈로그 매핑 (v1.6)
DEFECT_CODE_CATALOG: dict[str, list[str]] = {
    INSPECTION_KIND_FIRE_WORK: DEFECT_CODES_FIRE_WORK,
    INSPECTION_KIND_CONTAINER: DEFECT_CODES_CONTAINER,
}


def defect_codes_for(inspection_kind: str) -> list[str]:
    """주어진 점검 종류의 불량 사유 카탈로그. 매핑 없으면 빈 리스트."""
    return list(DEFECT_CODE_CATALOG.get(inspection_kind, []))


# ---------- v1.7: 세부 점검 checklist 카탈로그 ----------
# 각 점검 종류의 상세 점검 항목을 카테고리별로 정의. 점검자는 각 항목에 대해
# OK / NG / NA(해당없음)를 기록. NG가 하나라도 있으면 자동으로 결과 "불량" 힌트.

# 화기작업구간 점검 — 4 카테고리 × 3 세부 = 12개
CHECKLIST_FIRE_WORK: dict[str, list[str]] = {
    "방화포·소화기 비치": [
        "방화포 즉시 사용 가능 상태 비치",
        "소화기 인근 충분 비치",
        "방화포·소화기 상태 점검 통과 (손상·충전 압력)",
    ],
    "화재감시자 업무 숙련도": [
        "전담 감시자 배치",
        "업무 인지·숙련",
        "감시 위치 적절 (구간 조망 가능)",
    ],
    "가연물 정리정돈": [
        "반경 내 가연물 제거 또는 방화포 보양",
        "우발 접촉 위험 없이 정돈",
        "작업구간·주변 청소 상태",
    ],
    "주변 간섭사항": [
        "인접 지역 다른 공사 없음",
        "통행 차단·표시",
        "환기 충분 (연기·가스 정체 없음)",
    ],
}

# 가설컨테이너 사무실 점검 — 7개 항목 (카테고리 없이 단일 리스트)
CHECKLIST_CONTAINER: list[str] = [
    "소화기 비치·점검 상태 (내부 확산 + 외부 3.3kg)",
    "환기팬 설치기준 준수 (철제 팬·전원버튼)",
    "외부 차단기 설치 + 차단기함 시건",
    "감지기 작동 상태",
    "접지 상태",
    "철제쓰레기통 사용 + 인화성물질 보관",
    "일일점검체크리스트 작성",
]


def checklist_for(inspection_kind: str) -> dict[str, list[str]] | list[str] | None:
    """주어진 점검 종류의 세부 checklist 카탈로그.
    화기작업 → dict (카테고리별 항목 리스트)
    가설컨테이너 → list (단일 리스트)
    매핑 없음 → None
    """
    if inspection_kind == INSPECTION_KIND_FIRE_WORK:
        return CHECKLIST_FIRE_WORK
    if inspection_kind == INSPECTION_KIND_CONTAINER:
        return CHECKLIST_CONTAINER
    return None


def checklist_flat_keys(inspection_kind: str) -> list[str]:
    """checklist_items dict의 키 목록을 평탄화해 반환.
    화기작업: '카테고리|항목' 형식.
    가설컨테이너: 항목 그대로.
    """
    catalog = checklist_for(inspection_kind)
    if catalog is None:
        return []
    if isinstance(catalog, dict):
        return [f"{cat}|{item}" for cat, items in catalog.items() for item in items]
    return list(catalog)


@dataclass
class InspectionTask:
    task_id: str
    equipment_label: str
    task_type: str
    assignee: str
    due_date: date
    status: TaskStatus
    floor: str
    zone: str
    note: str = ""
    # v1.4: 점검 회차 FK + 제외 로그
    round_id: str | None = None
    excluded: bool = False
    excluded_at: date | None = None
    excluded_by: str | None = None
    excluded_reason: str = ""


@dataclass
class InspectionRound:
    """점검 회차. 신규 일정 등록 시 1개 회차 + N개 Task가 함께 생성됨."""
    round_id: str
    task_type: str
    assignee: str
    due_date: date
    status: TaskStatus
    note: str = ""
    cancelled: bool = False
    cancel_reason: str = ""
    cancelled_at: date | None = None
    cancelled_by: str = ""


@dataclass
class Deficiency:
    """별지5 안전점검 결과 지적내역서 row.
    v1.5: 별지6 통보서의 조치 단계 필드를 흡수 (action_*, submitter).
    v1.6: 화기작업·가설컨테이너 점검을 위한 불량 사유 카탈로그 (defect_codes/defect_other)."""
    deficiency_id: str
    inspection_date: date
    inspector: str
    floor: str
    zone: str
    inspection_types: list[InspectionType]
    issue: str
    resolution: ResolutionStatus
    confirmer: str | None
    notice_no: str | None
    task_id: str | None = None
    # v1.5: 조치 단계 (별지6 흡수)
    action_done: bool = False
    action_at: date | None = None
    action_note: str = ""
    action_photo_path: str | None = None
    submitter: str | None = None
    # v1.6: 불량 사유 카탈로그 (multiselect) + 기타 상세
    defect_codes: list[str] = None  # type: ignore[assignment]
    defect_other: str = ""
    # v1.7: 세부 checklist 항목별 상태 — {"카테고리|항목" or "항목": "OK"|"NG"|"NA"}
    checklist_items: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.defect_codes is None:
            self.defect_codes = []
        if self.checklist_items is None:
            self.checklist_items = {}


@dataclass
class Notice:
    """별지6 안전점검 조치 결과 통보서."""
    notice_no: str
    inspection_date: date
    floor: str
    zone: str
    inspection_type: InspectionType
    issue: str
    photo_path: str | None
    submitter: str
    confirmer: str
    # 조치 단계 (점검 발급 후 조치 담당자가 추후 채움)
    action_done: bool = False
    action_at: date | None = None
    action_note: str = ""
    action_photo: bytes | None = None       # 메모리 캐시 (업로드 직후)
    action_photo_path: str | None = None    # Storage 내 경로
    task_id: str | None = None              # v1.4: 점검 회차의 Task에 자동 매핑


@dataclass
class Malfunction:
    """별지9 소방시설 오동작 관리대장 row.
    v1.5+: 등록(detail까지)과 조치(action_*)를 분리 — 작업 조치 관리에서 후속 조치 입력."""
    malfunction_id: str
    category: EquipmentCategory
    occurred_on: date
    detail: str
    action: str
    confirmer: str
    task_id: str | None = None  # v1.4: 점검 회차의 Task에 자동 매핑
    action_done: bool = False    # v1.5+: 조치 완료 여부
    action_at: date | None = None
    action_note: str = ""


# ---------- Supabase 클라이언트 ----------

@st.cache_resource
def _db() -> Client:
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["service_role_key"])


def _d(s: str | None) -> date | None:
    """ISO 문자열 → date (None 허용).
    Supabase는 timestamptz 컬럼을 '2026-06-20T00:00:00+00:00' 형태로 반환하는데
    date.fromisoformat은 timezone offset을 못 받으므로 datetime 부분을 잘라낸다."""
    if not s:
        return None
    # 'T' 또는 공백이 있으면 datetime 형식 — 앞 10글자(YYYY-MM-DD)만 사용
    if "T" in s or " " in s:
        return date.fromisoformat(s[:10])
    return date.fromisoformat(s)


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


# ---------- 기준 날짜 ----------

# 앱 프로세스 시작 시점 기준 (자정을 넘겨 장시간 구동 시 재시작 필요)
TODAY = date.today()


# ---------- 도면 layout 정의 (각 층의 zone 사각형) ----------
# 각 항목: (zone_label, x, y, w, h)  좌표/크기는 0~100 정규화
FLOOR_LAYOUTS: dict[str, list[tuple[str, int, int, int, int]]] = {
    "B3": [("SEC1", 5, 60, 30, 30), ("SEC2", 35, 60, 30, 30), ("SEC3", 65, 60, 30, 30),
           ("SEC4", 65, 5, 30, 50), ("LOBBY", 5, 5, 60, 50)],
    "L1": [("HALL", 35, 35, 30, 30), ("LOB", 5, 60, 30, 30), ("ENT", 65, 60, 30, 30),
           ("RM-A", 5, 5, 30, 50), ("RM-B", 65, 5, 30, 50)],
    "L2": [("HVAC", 30, 10, 40, 30), ("OFFICE", 5, 45, 90, 50)],
    "B1": [("MECH", 20, 5, 30, 30), ("ELEC", 50, 5, 30, 30), ("STOR", 5, 40, 90, 55)],
    "B2": [("A", 5, 5, 30, 90), ("B", 35, 5, 30, 90), ("C", 45, 25, 25, 40), ("D", 70, 5, 25, 90)],
    "P4": [("PARK", 5, 30, 90, 65), ("ENT", 5, 5, 30, 22), ("EXIT", 65, 5, 30, 22)],
    "2F": [("A", 5, 5, 30, 30), ("B", 35, 5, 30, 30), ("C", 65, 5, 30, 30),
           ("D", 60, 18, 30, 30), ("E", 5, 50, 30, 45), ("F", 35, 50, 30, 45), ("G", 65, 50, 30, 45)],
    "4F": [("A", 5, 18, 30, 30), ("B", 35, 18, 30, 30), ("C", 65, 18, 30, 30),
           ("D", 5, 55, 30, 40), ("E", 35, 55, 30, 40), ("F", 65, 55, 30, 40)],
    "5F": [("A", 5, 5, 30, 30), ("B", 35, 5, 30, 30), ("C", 65, 5, 30, 30),
           ("D", 5, 40, 30, 30), ("E", 35, 40, 30, 30), ("F", 65, 40, 30, 30),
           ("G", 50, 68, 30, 25), ("H", 5, 70, 40, 25)],
    "6F": [("A", 5, 5, 30, 30), ("B", 35, 5, 30, 30), ("C", 65, 5, 30, 30),
           ("D", 5, 40, 30, 30), ("E", 35, 40, 30, 30), ("F", 65, 40, 30, 30),
           ("G", 5, 75, 60, 22), ("H", 65, 50, 30, 30)],
    "SRV": [("A", 5, 25, 45, 60), ("B", 50, 25, 45, 60), ("CTRL", 5, 5, 90, 15)],
}


def floor_layout(floor: str) -> list[tuple[str, int, int, int, int]]:
    """주어진 층의 zone 레이아웃을 반환 (없으면 빈 도면)."""
    return FLOOR_LAYOUTS.get(floor, [])


# ---------- row ↔ dataclass 변환 ----------

def _row_to_equipment(r: dict) -> Equipment:
    return Equipment(
        equipment_id=r["equipment_id"], location_id=r["location_id"],
        category=r["category"], equipment_name=r["equipment_name"],
        serial=r["serial"], qr_status=r["qr_status"],
        last_inspection=_d(r.get("last_inspection")),
        health_status=r["health_status"], floor=r["floor"], zone=r["zone"],
        pixel_x=r.get("pixel_x") or 0.0, pixel_y=r.get("pixel_y") or 0.0,
        inspection_types=list(r.get("inspection_types") or []),
        spot_id=r.get("spot_id"),
    )


def _row_to_spot(r: dict) -> Spot:
    return Spot(
        spot_id=r["spot_id"], floor=r["floor"],
        room_name=r["room_name"], notes=r.get("notes") or "",
        x_pct=float(r.get("x_pct") or 0.0),
        y_pct=float(r.get("y_pct") or 0.0),
        is_temporary=bool(r.get("is_temporary") or False),
    )


def _row_to_task(r: dict) -> InspectionTask:
    return InspectionTask(
        task_id=r["task_id"], equipment_label=r["equipment_label"],
        task_type=r["task_type"], assignee=r["assignee"],
        due_date=_d(r["due_date"]), status=r["status"],
        floor=r["floor"], zone=r["zone"], note=r.get("note") or "",
        round_id=r.get("round_id"),
        excluded=bool(r.get("excluded") or False),
        excluded_at=_d(r.get("excluded_at")),
        excluded_by=r.get("excluded_by"),
        excluded_reason=r.get("excluded_reason") or "",
    )


def _row_to_round(r: dict) -> InspectionRound:
    return InspectionRound(
        round_id=r["round_id"], task_type=r["task_type"],
        assignee=r.get("assignee") or "",
        due_date=_d(r["due_date"]),
        status=r["status"], note=r.get("note") or "",
        cancelled=bool(r.get("cancelled", False)),
        cancel_reason=r.get("cancel_reason") or "",
        cancelled_at=_d(r.get("cancelled_at")),
        cancelled_by=r.get("cancelled_by") or "",
    )


def _row_to_deficiency(r: dict) -> Deficiency:
    return Deficiency(
        deficiency_id=r["deficiency_id"], inspection_date=_d(r["inspection_date"]),
        inspector=r["inspector"], floor=r["floor"], zone=r["zone"],
        inspection_types=list(r.get("inspection_types") or []),
        issue=r["issue"], resolution=r["resolution"],
        confirmer=r.get("confirmer"), notice_no=r.get("notice_no"),
        task_id=r.get("task_id"),
        action_done=bool(r.get("action_done") or False),
        action_at=_d(r.get("action_at")),
        action_note=r.get("action_note") or "",
        action_photo_path=r.get("action_photo_path"),
        submitter=r.get("submitter"),
        defect_codes=list(r.get("defect_codes") or []),  # v1.6
        defect_other=r.get("defect_other") or "",        # v1.6
        checklist_items=dict(r.get("checklist_items") or {}),  # v1.7
    )


def _row_to_notice(r: dict) -> Notice:
    return Notice(
        notice_no=r["notice_no"], inspection_date=_d(r["inspection_date"]),
        floor=r["floor"], zone=r["zone"], inspection_type=r["inspection_type"],
        issue=r["issue"], photo_path=r.get("photo_path"),
        submitter=r["submitter"], confirmer=r["confirmer"],
        action_done=r.get("action_done") or False,
        action_at=_d(r.get("action_at")),
        action_note=r.get("action_note") or "",
        action_photo=None,
        action_photo_path=r.get("action_photo_path"),
        task_id=r.get("task_id"),
    )


def _row_to_malfunction(r: dict) -> Malfunction:
    return Malfunction(
        malfunction_id=r["malfunction_id"], category=r["category"],
        occurred_on=_d(r["occurred_on"]), detail=r["detail"],
        action=r.get("action") or "", confirmer=r.get("confirmer") or "",
        task_id=r.get("task_id"),
        action_done=bool(r.get("action_done") or False),
        action_at=_d(r.get("action_at")),
        action_note=r.get("action_note") or "",
    )


# ---------- 조회 (캐시) ----------

@st.cache_data(ttl=_CACHE_TTL)
def _equipment_rows() -> list[dict]:
    return _db().table("equipment").select("*").order("equipment_id").execute().data


@st.cache_data(ttl=_CACHE_TTL)
def _task_rows() -> list[dict]:
    return _db().table("inspection_tasks").select("*").order("due_date").execute().data


@st.cache_data(ttl=_CACHE_TTL)
def _deficiency_rows() -> list[dict]:
    return (_db().table("deficiencies").select("*")
            .order("inspection_date", desc=True).execute().data)


@st.cache_data(ttl=_CACHE_TTL)
def _notice_rows() -> list[dict]:
    return (_db().table("notices").select("*")
            .order("inspection_date", desc=True).execute().data)


@st.cache_data(ttl=_CACHE_TTL)
def _malfunction_rows() -> list[dict]:
    return (_db().table("malfunctions").select("*")
            .order("occurred_on", desc=True).execute().data)


@st.cache_data(ttl=_CACHE_TTL)
def _spot_rows() -> list[dict]:
    return (_db().table("floor_spots").select("*")
            .order("floor").order("spot_id").execute().data)


@st.cache_data(ttl=_CACHE_TTL)
def _round_rows() -> list[dict]:
    return (_db().table("inspection_rounds").select("*")
            .order("due_date", desc=True).execute().data)


@st.cache_data(ttl=_CACHE_TTL)
def _inspection_type_rows() -> list[dict]:
    """점검 유형 카탈로그 조회. 테이블 미존재/오류 시 [] → 하드코딩 폴백 신호."""
    try:
        return (_db().table("inspection_types").select("*")
                .order("sort_order").order("name").execute().data)
    except Exception:
        return []


def inspection_types_table_exists() -> bool:
    """관리 UI에서 마이그레이션 안내 분기용."""
    try:
        _db().table("inspection_types").select("name").limit(1).execute()
        return True
    except Exception:
        return False


def load_equipment() -> list[Equipment]:
    return [_row_to_equipment(r) for r in _equipment_rows()]


def load_tasks() -> list[InspectionTask]:
    return [_row_to_task(r) for r in _task_rows()]


def load_deficiencies() -> list[Deficiency]:
    return [_row_to_deficiency(r) for r in _deficiency_rows()]


def load_notices() -> list[Notice]:
    return [_row_to_notice(r) for r in _notice_rows()]


def load_malfunctions() -> list[Malfunction]:
    return [_row_to_malfunction(r) for r in _malfunction_rows()]


def load_spots(floor: str | None = None) -> list[Spot]:
    """전체 spot 또는 특정 층의 spot 목록."""
    rows = _spot_rows()
    if floor is not None:
        rows = [r for r in rows if r["floor"] == floor]
    return [_row_to_spot(r) for r in rows]


def get_spot(spot_id: str) -> Spot | None:
    for r in _spot_rows():
        if r["spot_id"] == spot_id:
            return _row_to_spot(r)
    return None


def load_rounds() -> list[InspectionRound]:
    return [_row_to_round(r) for r in _round_rows()]


def load_inspection_types(active_only: bool = False) -> list[str]:
    """점검 유형 이름 목록. 테이블 없으면 하드코딩 TASK_INSPECTION_TYPES 폴백."""
    rows = _inspection_type_rows()
    if not rows:
        return list(TASK_INSPECTION_TYPES)
    if active_only:
        rows = [r for r in rows if r.get("is_active", True)]
    return [r["name"] for r in rows]


def load_inspection_type_rows() -> list[dict]:
    """관리 UI용 유형 행 목록. 테이블 없으면 하드코딩 5종을 기본(builtin)으로 합성."""
    rows = _inspection_type_rows()
    if rows:
        return rows
    return [
        {"name": n, "is_active": True, "is_builtin": True, "sort_order": i + 1}
        for i, n in enumerate(TASK_INSPECTION_TYPES)
    ]


def get_round(round_id: str) -> InspectionRound | None:
    for r in _round_rows():
        if r["round_id"] == round_id:
            return _row_to_round(r)
    return None


def tasks_of_round(round_id: str, include_excluded: bool = False) -> list[InspectionTask]:
    """회차에 속한 Task 목록. 기본은 제외된 Task 빼고 반환."""
    items = [t for t in load_tasks() if t.round_id == round_id]
    if not include_excluded:
        items = [t for t in items if not t.excluded]
    return items


def round_progress(round_id: str) -> tuple[int, int]:
    """(완료된 Task 수, 전체 Task 수). 제외된 Task는 제외."""
    tasks = tasks_of_round(round_id)
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "Completed")
    return done, total


def compute_round_status(round_id: str) -> str:
    """회차의 자동 status 계산.
    - 모든 Task Completed → Completed
    - Overdue Task 1+ → Overdue
    - In Progress Task 1+ → In Progress
    - 그 외 → Scheduled
    제외된 Task는 분모에서 빠짐. Task가 0건이면 Scheduled 반환.
    취소된 회차는 status를 재계산하지 않는다(현재 status 유지)."""
    _r = get_round(round_id)
    if _r and _r.cancelled:
        return _r.status
    tasks = tasks_of_round(round_id)
    if not tasks:
        return "Scheduled"
    if all(t.status == "Completed" for t in tasks):
        return "Completed"
    if any(t.status == "Overdue" for t in tasks):
        return "Overdue"
    if any(t.status == "In Progress" for t in tasks):
        return "In Progress"
    return "Scheduled"


# ---------- 쓰기 ----------

def add_equipment(e: Equipment) -> None:
    _db().table("equipment").insert({
        "equipment_id": e.equipment_id, "location_id": e.location_id,
        "category": e.category, "equipment_name": e.equipment_name,
        "serial": e.serial, "qr_status": e.qr_status,
        "last_inspection": _iso(e.last_inspection),
        "health_status": e.health_status, "floor": e.floor, "zone": e.zone,
        "pixel_x": e.pixel_x, "pixel_y": e.pixel_y,
        "inspection_types": e.inspection_types or [],
        "spot_id": e.spot_id,
    }).execute()
    _equipment_rows.clear()


def add_spot(s: Spot) -> None:
    _db().table("floor_spots").insert({
        "spot_id": s.spot_id, "floor": s.floor,
        "room_name": s.room_name, "notes": s.notes,
        "x_pct": s.x_pct, "y_pct": s.y_pct,
        "is_temporary": s.is_temporary,
    }).execute()
    _spot_rows.clear()


def update_spot(s: Spot) -> None:
    _db().table("floor_spots").update({
        "floor": s.floor, "room_name": s.room_name,
        "notes": s.notes, "x_pct": s.x_pct, "y_pct": s.y_pct,
        "is_temporary": s.is_temporary,
    }).eq("spot_id", s.spot_id).execute()
    _spot_rows.clear()


def update_spot_with_equipment_sync(s: Spot) -> int:
    """spot 갱신 + 이 spot에 매핑된 모든 장비의 pixel_x/y/zone 동기화.
    반환값은 동기화된 장비 행 수."""
    _db().table("floor_spots").update({
        "floor": s.floor, "room_name": s.room_name,
        "notes": s.notes, "x_pct": s.x_pct, "y_pct": s.y_pct,
        "is_temporary": s.is_temporary,
    }).eq("spot_id", s.spot_id).execute()
    res = _db().table("equipment").update({
        "pixel_x": s.x_pct, "pixel_y": s.y_pct,
        "zone": s.room_name,
    }).eq("spot_id", s.spot_id).execute()
    _spot_rows.clear()
    _equipment_rows.clear()
    return len(res.data or [])


def delete_spot(spot_id: str) -> None:
    """spot 삭제. 이 spot을 참조하던 장비는 spot_id가 NULL로 풀린다 (FK 미설정).
    호출 전 사용 중 여부를 확인해서 사용자에게 경고할 책임은 호출부에 있다."""
    _db().table("equipment").update({"spot_id": None}).eq("spot_id", spot_id).execute()
    _db().table("floor_spots").delete().eq("spot_id", spot_id).execute()
    _equipment_rows.clear()
    _spot_rows.clear()


def next_spot_id(floor: str) -> str:
    """다음 spot ID (SPOT-{floor}-NNN). 같은 층 내 순번."""
    existing = [r["spot_id"] for r in _spot_rows() if r["floor"] == floor]
    prefix = f"SPOT-{floor}-"
    max_n = _max_seq_in_ids(existing, prefix)
    return f"{prefix}{max_n + 1:03d}"


def location_id_from_spot(spot_id: str) -> str:
    """spot_id에서 사용자 가시 location_id를 파생. 형식 '{floor}-{nn}'.
    예: 'SPOT-1F-003' → '1F-03', 'SPOT-Roof-012' → 'Roof-12'.
    spot 형식이 아닌 경우 spot_id를 그대로 반환 (하위 호환)."""
    parts = spot_id.split("-")
    if len(parts) < 3 or parts[0] != "SPOT":
        return spot_id
    floor = parts[1]
    try:
        num = int(parts[-1])
    except ValueError:
        return spot_id
    return f"{floor}-{num:02d}"


def update_equipment_location(equipment_id: str, spot: Spot) -> None:
    """장비의 위치(spot)를 변경. spot 좌표·층·zone·location_id를 일괄 갱신."""
    _db().table("equipment").update({
        "spot_id": spot.spot_id,
        "floor": spot.floor,
        "zone": spot.room_name,
        "location_id": location_id_from_spot(spot.spot_id),
        "pixel_x": spot.x_pct,
        "pixel_y": spot.y_pct,
    }).eq("equipment_id", equipment_id).execute()
    _equipment_rows.clear()


def mark_qr_assigned(equipment_id: str) -> bool:
    """장비의 qr_status를 PENDING이면 ASSIGNED로 전환. 이미 ASSIGNED면 no-op.

    QR 첫 스캔(`?eq=...` 딥링크 진입) 시 호출 — "QR이 실제로 현장에 부착됐고
    누군가 스캔에 성공했다"는 신호로 간주. 반환값은 실제 전환이 일어났는지 여부.
    """
    rows = _db().table("equipment").select("qr_status").eq(
        "equipment_id", equipment_id
    ).execute().data
    if not rows or rows[0].get("qr_status") != "PENDING":
        return False
    _db().table("equipment").update(
        {"qr_status": "ASSIGNED"}
    ).eq("equipment_id", equipment_id).execute()
    _equipment_rows.clear()
    return True


def set_equipment_inspection_types(equipment_id: str, types: list[str]) -> None:
    """장비의 적용 점검 유형을 갱신."""
    _db().table("equipment").update(
        {"inspection_types": list(types)}
    ).eq("equipment_id", equipment_id).execute()
    _equipment_rows.clear()


# ---------- 점검 유형 카탈로그 관리 (v1.8) ----------

def _inspection_type_usage(name: str) -> int:
    """유형 사용량 = 장비 inspection_types 포함 수 + 회차 task_type 일치 수."""
    eq_cnt = sum(1 for e in load_equipment() if name in (e.inspection_types or []))
    rnd_cnt = sum(1 for r in load_rounds() if r.task_type == name)
    return eq_cnt + rnd_cnt


def add_inspection_type(name: str) -> tuple[bool, str]:
    """새 점검 유형 추가. (성공여부, 메시지)."""
    name = (name or "").strip()
    if not name:
        return False, "이름을 입력하세요."
    rows = _inspection_type_rows()
    if name in {r["name"] for r in rows}:
        return False, "이미 존재하는 유형입니다."
    max_order = max([r.get("sort_order", 0) for r in rows] or [0])
    _db().table("inspection_types").insert({
        "name": name, "is_active": True, "is_builtin": False,
        "sort_order": max_order + 1,
    }).execute()
    _inspection_type_rows.clear()
    return True, "추가되었습니다."


def set_inspection_type_active(name: str, active: bool) -> None:
    """유형 활성/비활성 전환."""
    _db().table("inspection_types").update(
        {"is_active": active}
    ).eq("name", name).execute()
    _inspection_type_rows.clear()


def delete_inspection_type(name: str) -> tuple[bool, str]:
    """유형 삭제. 기본·사용중 유형은 거부. (성공여부, 메시지)."""
    row = next((r for r in _inspection_type_rows() if r["name"] == name), None)
    if row and row.get("is_builtin"):
        return False, "기본 유형은 삭제할 수 없습니다."
    if _inspection_type_usage(name) > 0:
        return False, "사용 중인 유형은 삭제할 수 없습니다 (비활성만 가능)."
    _db().table("inspection_types").delete().eq("name", name).execute()
    _inspection_type_rows.clear()
    return True, "삭제되었습니다."


def record_equipment_inspection(equipment_id: str, inspected_on: date,
                                health: HealthStatus) -> None:
    """점검 제출 시 장비의 최근 점검일·건강 상태 갱신."""
    _db().table("equipment").update({
        "last_inspection": _iso(inspected_on),
        "health_status": health,
    }).eq("equipment_id", equipment_id).execute()
    _equipment_rows.clear()


def add_task(t: InspectionTask) -> None:
    _db().table("inspection_tasks").insert({
        "task_id": t.task_id, "equipment_label": t.equipment_label,
        "task_type": t.task_type, "assignee": t.assignee,
        "due_date": _iso(t.due_date), "status": t.status,
        "floor": t.floor, "zone": t.zone, "note": t.note,
        "round_id": t.round_id,
    }).execute()
    _task_rows.clear()


def add_round(r: InspectionRound) -> None:
    _db().table("inspection_rounds").insert({
        "round_id": r.round_id, "task_type": r.task_type,
        "assignee": r.assignee, "due_date": _iso(r.due_date),
        "status": r.status, "note": r.note,
    }).execute()
    _round_rows.clear()


def _refresh_round_status(round_id: str) -> None:
    """회차의 자동 status를 계산해 갱신. 취소된 회차는 갱신하지 않는다."""
    r = get_round(round_id)
    if r and r.cancelled:
        return
    new_status = compute_round_status(round_id)
    _db().table("inspection_rounds").update(
        {"status": new_status}
    ).eq("round_id", round_id).execute()
    _round_rows.clear()


def round_cancel_supported() -> bool:
    """inspection_rounds.cancelled 컬럼(마이그레이션) 존재 여부."""
    try:
        _db().table("inspection_rounds").select("cancelled").limit(1).execute()
        return True
    except Exception:
        return False


def cancel_round(round_id: str, reason: str, by: str) -> bool:
    """회차를 취소 처리(사유 기록). 완료·기취소 회차는 거부(False). 성공 시 True.
    취소 컬럼 미마이그레이션 등 DB 오류 시에도 False."""
    r = get_round(round_id)
    if not r or r.cancelled or r.status == "Completed":
        return False
    try:
        _db().table("inspection_rounds").update({
            "cancelled": True,
            "cancel_reason": (reason or "").strip(),
            "cancelled_at": _iso(TODAY),
            "cancelled_by": by or "",
        }).eq("round_id", round_id).execute()
    except Exception:
        return False
    _round_rows.clear()
    return True


def exclude_task(task_id: str, reason: str, by: str) -> None:
    """Task를 제외 (점검 대상에서 빼되 로그는 보존). 회차 status 자동 갱신."""
    from datetime import date as _date
    res = _db().table("inspection_tasks").update({
        "excluded": True,
        "excluded_at": _date.today().isoformat(),
        "excluded_by": by,
        "excluded_reason": reason,
    }).eq("task_id", task_id).execute()
    _task_rows.clear()
    # 해당 Task의 회차 status 재계산
    for r in (res.data or []):
        round_id = r.get("round_id")
        if round_id:
            _refresh_round_status(round_id)


def restore_task(task_id: str) -> None:
    """제외된 Task를 복구."""
    res = _db().table("inspection_tasks").update({
        "excluded": False,
        "excluded_at": None,
        "excluded_by": None,
        "excluded_reason": "",
    }).eq("task_id", task_id).execute()
    _task_rows.clear()
    for r in (res.data or []):
        if r.get("round_id"):
            _refresh_round_status(r["round_id"])


def next_round_id() -> str:
    """다음 점검 ID. 형식: INS-YYYYMMDD-NNN (오늘 날짜 + 일내 순번).
    UI에서는 '점검 ID'로 노출. v1.5+에서 prefix RND → INS로 변경."""
    today = TODAY.strftime("%Y%m%d")
    prefix = f"INS-{today}-"
    existing = [r["round_id"] for r in _round_rows()
                if r["round_id"].startswith(prefix)]
    next_n = len(existing) + 1
    return f"{prefix}{next_n:03d}"


def add_deficiency(d: Deficiency) -> None:
    _db().table("deficiencies").insert({
        "deficiency_id": d.deficiency_id,
        "inspection_date": _iso(d.inspection_date),
        "inspector": d.inspector, "floor": d.floor, "zone": d.zone,
        "inspection_types": list(d.inspection_types or []),
        "issue": d.issue, "resolution": d.resolution,
        "confirmer": d.confirmer, "notice_no": d.notice_no,
        "task_id": d.task_id,
        "action_done": d.action_done,
        "action_at": _iso(d.action_at),
        "action_note": d.action_note,
        "action_photo_path": d.action_photo_path,
        "submitter": d.submitter,
        "defect_codes": list(d.defect_codes or []),  # v1.6
        "defect_other": d.defect_other or "",        # v1.6
        "checklist_items": dict(d.checklist_items or {}),  # v1.7
    }).execute()
    _deficiency_rows.clear()


def record_deficiency_action(
    deficiency_id: str, action_at: date, action_note: str,
    confirmer: str, photo: bytes | None,
) -> None:
    """별지5 지적사항에 조치 단계 기록 (구 별지6 통보서 조치 흡수).
    사진은 action-photos 버킷에 업로드."""
    photo_path = None
    if photo:
        # 통보서 사진 키 컨벤션 재사용 (deficiency_id로 저장)
        photo_path = _upload_action_photo(deficiency_id, photo)
    payload = {
        "action_done": True,
        "action_at": _iso(action_at),
        "action_note": action_note,
        "confirmer": confirmer,
    }
    if photo_path:
        payload["action_photo_path"] = photo_path
    _db().table("deficiencies").update(payload).eq(
        "deficiency_id", deficiency_id
    ).execute()
    _deficiency_rows.clear()


def add_notice(n: Notice) -> None:
    photo_path = None
    if n.action_photo:
        photo_path = _upload_action_photo(n.notice_no, n.action_photo)
    _db().table("notices").insert({
        "notice_no": n.notice_no, "inspection_date": _iso(n.inspection_date),
        "floor": n.floor, "zone": n.zone,
        "inspection_type": n.inspection_type, "issue": n.issue,
        "photo_path": n.photo_path, "submitter": n.submitter,
        "confirmer": n.confirmer, "action_done": n.action_done,
        "action_at": _iso(n.action_at), "action_note": n.action_note,
        "task_id": n.task_id,
        "action_photo_path": photo_path,
    }).execute()
    _notice_rows.clear()


def add_malfunction(m: Malfunction) -> None:
    _db().table("malfunctions").insert({
        "malfunction_id": m.malfunction_id, "category": m.category,
        "occurred_on": _iso(m.occurred_on), "detail": m.detail,
        "action": m.action, "confirmer": m.confirmer,
        "task_id": m.task_id,
        "action_done": m.action_done,
        "action_at": _iso(m.action_at),
        "action_note": m.action_note,
    }).execute()
    _malfunction_rows.clear()


def record_malfunction_action(
    malfunction_id: str, action_at: date, action_note: str, confirmer: str,
) -> None:
    """오동작 조치 입력 — 작업 조치 관리에서 호출."""
    _db().table("malfunctions").update({
        "action_done": True,
        "action_at": _iso(action_at),
        "action_note": action_note,
        "confirmer": confirmer,
        "action": action_note,  # 기존 action 필드도 동기화
    }).eq("malfunction_id", malfunction_id).execute()
    _malfunction_rows.clear()


def complete_notice_action(notice_no: str, action_at: date, action_note: str,
                           confirmer: str, photo: bytes | None) -> None:
    """통보서의 후속 조치 완료 처리 (별지6). 사진은 Storage 업로드."""
    photo_path = _upload_action_photo(notice_no, photo) if photo else None
    payload = {
        "action_done": True,
        "action_at": _iso(action_at),
        "action_note": action_note,
        "confirmer": confirmer,
    }
    if photo_path:
        payload["action_photo_path"] = photo_path
    _db().table("notices").update(payload).eq("notice_no", notice_no).execute()
    _notice_rows.clear()


# ---------- 조치 사진 Storage ----------

def _upload_action_photo(notice_no: str, photo: bytes) -> str:
    """조치 사진을 Storage에 업로드하고 경로를 반환."""
    path = f"{notice_no.replace('/', '-')}.bin"
    _db().storage.from_(ACTION_PHOTO_BUCKET).upload(
        path, photo,
        {"content-type": "application/octet-stream", "upsert": "true"},
    )
    return path


def get_action_photo(n: Notice) -> bytes | None:
    """통보서의 조치 사진 바이트 (없으면 None). PDF 생성 시 사용."""
    if n.action_photo:
        return n.action_photo
    if not n.action_photo_path:
        return None
    try:
        return _db().storage.from_(ACTION_PHOTO_BUCKET).download(n.action_photo_path)
    except Exception:
        return None


# ---------- ID 채번 ----------

def _max_seq_in_ids(ids: list[str], prefix: str) -> int:
    """주어진 id 리스트에서 prefix 뒤 숫자 부분의 최대값. 없으면 0."""
    max_n = 0
    for eid in ids:
        if not eid.startswith(prefix):
            continue
        try:
            n = int(eid[len(prefix):].strip("-_ "))
            if n > max_n:
                max_n = n
        except ValueError:
            continue
    return max_n


def next_equipment_id() -> str:
    """다음 장비 ID (EQ-NNNN)."""
    ids = [e.equipment_id for e in load_equipment()]
    return f"EQ-{_max_seq_in_ids(ids, 'EQ-') + 1:04d}"


def next_serial(prefix: str = "PYRO") -> str:
    """다음 시리얼 번호 (PYRO-NNNNN)."""
    serials = [e.serial for e in load_equipment()]
    return f"{prefix}-{_max_seq_in_ids(serials, f'{prefix}-') + 1:05d}"


def next_location_id(floor: str, zone: str) -> str:
    """같은 층/구역의 다음 순번 위치 ID. 예: B3-SEC4-W3"""
    base = f"{floor}-{zone}-"
    existing = [e.location_id for e in load_equipment() if e.location_id.startswith(base)]
    # 위치 ID는 -W2, -01 등 다양한 패턴이라 단순히 카운트만
    return f"{base}W{len(existing) + 1}"


def next_task_id() -> str:
    """다음 점검 일정 ID (TSK-NNNN)."""
    ids = [t.task_id for t in load_tasks()]
    return f"TSK-{_max_seq_in_ids(ids, 'TSK-') + 1:04d}"


def next_deficiency_id() -> str:
    """다음 지적사항 ID (D-YYYY-NN)."""
    prefix = f"D-{TODAY.year}-"
    ids = [d.deficiency_id for d in load_deficiencies()]
    return f"{prefix}{_max_seq_in_ids(ids, prefix) + 1:02d}"


def next_malfunction_id() -> str:
    """다음 오동작 ID (M-NNN)."""
    ids = [m.malfunction_id for m in load_malfunctions()]
    return f"M-{_max_seq_in_ids(ids, 'M-') + 1:03d}"


def next_notice_no(d: date) -> str:
    """같은 날짜 내 순번을 자동 증가시켜 YYYY-MM-DD-NN 형식 반환."""
    prefix = d.isoformat()
    existing = [n.notice_no for n in load_notices() if n.notice_no.startswith(prefix)]
    next_n = len(existing) + 1
    return f"{prefix}-{next_n:02d}"


# ---------- 집계 (KPI) ----------

def equipment_kpis() -> dict:
    eq_rows = _equipment_rows()
    eq = [_row_to_equipment(r) for r in eq_rows]
    recent_threshold = TODAY - timedelta(days=2)
    month_start = TODAY.replace(day=1)
    new_this_month = 0
    for r in eq_rows:
        created = r.get("created_at")
        if created and datetime.fromisoformat(created).date() >= month_start:
            new_this_month += 1
    pending = sum(1 for e in eq if e.health_status in ("FAIL", "DUE"))
    assigned = sum(1 for e in eq if e.qr_status == "ASSIGNED")
    return {
        "total": len(eq),
        "new_this_month": new_this_month,
        "recently_inspected": sum(
            1 for e in eq
            if e.last_inspection and e.last_inspection >= recent_threshold
        ),
        "pending_issues": pending,
        "qr_coverage": (assigned / len(eq)) * 100 if eq else 0,
    }


def notice_action_rate() -> float | None:
    """조치 완료 통보서 ÷ 발급 통보서 (누적). 통보서 0건이면 None."""
    notices = load_notices()
    if not notices:
        return None
    return sum(1 for n in notices if n.action_done) / len(notices) * 100


def task_kpis() -> dict:
    tasks = load_tasks()
    return {
        "total": len(tasks),
        "overdue": sum(1 for t in tasks if t.status == "Overdue"),
        "in_progress": sum(1 for t in tasks if t.status == "In Progress"),
        "completed": sum(1 for t in tasks if t.status == "Completed"),
    }


def field_kpis() -> dict:
    tasks = load_tasks()
    defs = load_deficiencies()
    return {
        "inspections_today": sum(1 for t in tasks if t.due_date == TODAY),
        "pending_deficiencies": sum(1 for d in defs if d.resolution == "불가"),
    }


# ---------- 시드 데이터 (seed_supabase.py 최초 이전용) ----------

def _seed_equipment() -> list[Equipment]:
    """장비 시드. 마지막 두 인자는 도면 정규화 좌표(0~100). zone 위치에 맞춰 배치."""
    raw = [
        Equipment("EQ-0001", "B3-SEC4-W2", "소화기", "ABC Extinguisher (5kg)", "PYRO-94821", "ASSIGNED", TODAY - timedelta(days=45), "PASS", "B3", "SEC4", 78, 22),
        Equipment("EQ-0002", "L1-HALL-E1", "소화기", "CO2 Fire Extinguisher", "PYRO-88210", "PENDING", TODAY - timedelta(days=59), "FAIL", "L1", "HALL", 50, 50),
        Equipment("EQ-0003", "B1-MECH-01", "소화전", "Fire Hose Cabinet", "PYRO-11203", "ASSIGNED", TODAY - timedelta(days=42), "DUE", "B1", "MECH", 32, 18),
        Equipment("EQ-0004", "P4-PARK-S9", "소화기", "ABC Extinguisher (9kg)", "PYRO-55421", "ASSIGNED", TODAY - timedelta(days=56), "PASS", "P4", "PARK", 65, 70),
        Equipment("EQ-0005", "2F-D-01", "간이피난유도선", "간이피난유도선 #2-D-01", "PYRO-22011", "ASSIGNED", TODAY - timedelta(days=15), "FAIL", "2F", "D", 70, 30),
        Equipment("EQ-0006", "4F-A-03", "소화기", "대형소화기 운반수레", "PYRO-40031", "ASSIGNED", TODAY - timedelta(days=15), "FAIL", "4F", "A", 22, 28),
        Equipment("EQ-0007", "5F-G-02", "감지기", "광전식 연기감지기", "PYRO-50220", "ASSIGNED", TODAY - timedelta(days=1), "PASS", "5F", "G", 65, 78),
        Equipment("EQ-0008", "6F-H-04", "방화포", "방화포 #6-H-04", "PYRO-60440", "ASSIGNED", TODAY - timedelta(days=15), "DUE", "6F", "H", 82, 60),
        Equipment("EQ-0009", "SRV-A-01", "스프링클러", "Sprinkler Grid - Server Room A", "PYRO-71010", "ASSIGNED", TODAY - timedelta(days=120), "DUE", "SRV", "A", 25, 50),
        Equipment("EQ-0010", "HVAC-L2-S", "감지기", "Smoke Detector - HVAC Level 2", "PYRO-72120", "ASSIGNED", TODAY - timedelta(days=80), "DUE", "L2", "HVAC", 50, 25),
        Equipment("EQ-0011", "LOB-EXT-A", "소화기", "Lobby Extinguisher A", "PYRO-73130", "ASSIGNED", TODAY - timedelta(days=1), "PASS", "L1", "LOB", 28, 75),
        Equipment("EQ-0012", "B2-EXT-04", "비상경보장치", "비상경보장치 #B2-04", "PYRO-74140", "PENDING", None, "DUE", "B2", "C", 55, 40),
    ]
    for e in raw:
        if not e.inspection_types:
            e.inspection_types = default_inspection_types_for(e.category)
    return raw


def _seed_tasks() -> list[InspectionTask]:
    return [
        InspectionTask("TSK-1042", "Server Room A - Sprinkler Grid", "Sprinkler Test", "J. Smith", TODAY - timedelta(days=15), "Overdue", "SRV", "A"),
        InspectionTask("TSK-1045", "Lobby - Fire Extinguishers", "Monthly Extinguisher", "A. Park", TODAY + timedelta(days=2), "In Progress", "L1", "LOB"),
        InspectionTask("TSK-1050", "HVAC Level 2 - Smoke Detectors", "Smoke Detector Check", "Unassigned", TODAY + timedelta(days=8), "Scheduled", "L2", "HVAC"),
        InspectionTask("TSK-1051", "Floor 4 - Extinguisher Audit", "Monthly Extinguisher", "박소방", TODAY, "In Progress", "4F", "A"),
        InspectionTask("TSK-1052", "Main Lobby - Sprinkler Test", "Sprinkler Test", "박소방", TODAY + timedelta(days=1), "Scheduled", "L1", "LOB"),
        InspectionTask("TSK-1053", "Server Room B - Smoke Sensor", "Smoke Detector Check", "박소방", TODAY - timedelta(days=1), "Completed", "SRV", "B"),
        InspectionTask("TSK-1054", "2F - 피난로 점검", "피난로 등", "박소방", TODAY - timedelta(days=2), "Completed", "2F", "D"),
        InspectionTask("TSK-1055", "5F - 임시소방시설 점검", "임시소방시설", "박소방", TODAY - timedelta(days=15), "Completed", "5F", "G"),
        InspectionTask("TSK-1056", "6F - 화기취급감독", "화기취급감독", "홍길동", TODAY - timedelta(days=15), "Completed", "6F", "H"),
        InspectionTask("TSK-1057", "B3 - 소화기 정기점검", "Monthly Extinguisher", "박소방", TODAY + timedelta(days=3), "Scheduled", "B3", "SEC4"),
    ]


def _seed_deficiencies() -> list[Deficiency]:
    """불량 항목은 모두 통보서 번호를 보유 (즉시 완료/후속 대기 모두)."""
    return [
        Deficiency("D-2025-01", date(2025, 5, 12), "박소방", "2F", "D",
                   ["임시소방시설"], "1-A계단 피난구 유도등 점등 불량", "완료", "박소방", "2025-05-12-02"),
        Deficiency("D-2025-02", date(2025, 5, 12), "박소방", "4F", "A",
                   ["임시소방시설"], "대형소화기 운반수레 바퀴 파손", "완료", "홍길동", "2025-05-12-03"),
        Deficiency("D-2025-03", date(2025, 5, 12), "박소방", "5F", "G",
                   ["피난로 등"], "2-A 계단앞 물건 적재", "불가", "박소방", "2026-05-12-01"),
        Deficiency("D-2025-04", date(2025, 5, 12), "박소방", "6F", "H",
                   ["화기취급감독"], "가연성 자재 옆 흡연", "완료", "가나다", "2025-05-12-04"),
        # 후속 조치 대기 중 (통보서 2026-05-27-01 연결)
        Deficiency("D-2026-05", date(2026, 5, 27), "박소방", "4F", "A",
                   ["임시소방시설"], "대형소화기 운반수레 바퀴 파손 (재발)",
                   "불가", None, "2026-05-27-01"),
    ]


def _seed_notices() -> list[Notice]:
    """모든 불량 항목은 통보서를 가짐. 점검자가 현장 즉시 조치한 건도 통보서 발급+즉시 완료."""
    return [
        # 후속 조치 대기 (4F/A 바퀴 파손 재발)
        Notice("2026-05-27-01", date(2026, 5, 27), "4F", "A", "임시소방시설",
               "대형소화기 운반수레 바퀴 파손 (재발)", None, "박소방", "김소장",
               action_done=False),
        # 후속 조치 완료 (5F/G 물건 적재 — 조치자가 처리)
        Notice("2026-05-12-01", date(2026, 5, 12), "5F", "G", "피난로 등",
               "2-A 계단 앞 물건 적재", None, "박소방", "김소장",
               action_done=True, action_at=date(2026, 5, 13),
               action_note="물건 이동 완료"),
        # 점검자 현장 즉시 조치 (2F/D 유도등 점등 불량)
        Notice("2025-05-12-02", date(2025, 5, 12), "2F", "D", "임시소방시설",
               "1-A계단 피난구 유도등 점등 불량", None, "박소방", "박소방",
               action_done=True, action_at=date(2025, 5, 12),
               action_note="현장에서 즉시 전구 교체"),
        # 점검자 현장 즉시 조치 (4F/A 바퀴 파손 — 첫 회)
        Notice("2025-05-12-03", date(2025, 5, 12), "4F", "A", "임시소방시설",
               "대형소화기 운반수레 바퀴 파손", None, "박소방", "홍길동",
               action_done=True, action_at=date(2025, 5, 12),
               action_note="여분 바퀴로 교체"),
        # 점검자 현장 즉시 조치 (6F/H 흡연)
        Notice("2025-05-12-04", date(2025, 5, 12), "6F", "H", "화기취급감독",
               "가연성 자재 옆 흡연", None, "박소방", "가나다",
               action_done=True, action_at=date(2025, 5, 12),
               action_note="흡연자에게 중단 요청, 흡연 구역 안내"),
    ]


def _seed_malfunctions() -> list[Malfunction]:
    return [
        Malfunction("M-001", "간이피난유도선", date(2026, 5, 12), "점등 불량", "교체", "박소방"),
        Malfunction("M-002", "간이소화장치", date(2026, 5, 13), "충수 상태 불량", "수원공급", "정안전"),
    ]
