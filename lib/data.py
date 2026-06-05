"""Mock data layer. 추후 Supabase로 교체할 수 있도록 함수 시그니처를 유지한다."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import streamlit as st

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


@dataclass
class Deficiency:
    """별지5 안전점검 결과 지적내역서 row."""
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
    action_photo: bytes | None = None  # 업로드된 사진 바이트


@dataclass
class Malfunction:
    """별지9 소방시설 오동작 관리대장 row."""
    malfunction_id: str
    category: EquipmentCategory
    occurred_on: date
    detail: str
    action: str
    confirmer: str


# ---------- 시드 데이터 ----------

TODAY = date(2026, 5, 27)


def _seed_equipment() -> list[Equipment]:
    """장비 시드. 마지막 두 인자는 도면 정규화 좌표(0~100). zone 위치에 맞춰 배치."""
    return [
        Equipment("EQ-0001", "B3-SEC4-W2", "소화기", "ABC Extinguisher (5kg)", "PYRO-94821", "ASSIGNED", TODAY - timedelta(days=45), "PASS", "B3", "SEC4", 78, 22),
        Equipment("EQ-0002", "L1-HALL-E1", "소화기", "CO2 Fire Extinguisher", "PYRO-88210", "PENDING", TODAY - timedelta(days=59), "FAIL", "L1", "HALL", 50, 50),
        Equipment("EQ-0003", "B1-MECH-01", "소화전", "Fire Hose Cabinet", "PYRO-11203", "ASSIGNED", TODAY - timedelta(days=42), "DUE", "B1", "MECH", 32, 18),
        Equipment("EQ-0004", "P4-PARK-S9", "소화기", "ABC Extinguisher (9kg)", "PYRO-55421", "ASSIGNED", TODAY - timedelta(days=56), "PASS", "P4", "PARK", 65, 70),
        Equipment("EQ-0005", "2F-D-01", "간이피난유도선", "간이피난유도선 #2-D-01", "PYRO-22011", "ASSIGNED", TODAY - timedelta(days=15), "FAIL", "2F", "D", 70, 30),
        Equipment("EQ-0006", "4F-A-03", "소화기", "대형소화기 운반수레", "PYRO-40031", "ASSIGNED", TODAY - timedelta(days=15), "FAIL", "4F", "A", 22, 28),
        Equipment("EQ-0007", "5F-G-02", "감지기", "광전식 연기감지기", "PYRO-50220", "ASSIGNED", TODAY - timedelta(days=15), "PASS", "5F", "G", 65, 78),
        Equipment("EQ-0008", "6F-H-04", "방화포", "방화포 #6-H-04", "PYRO-60440", "ASSIGNED", TODAY - timedelta(days=15), "DUE", "6F", "H", 82, 60),
        Equipment("EQ-0009", "SRV-A-01", "스프링클러", "Sprinkler Grid - Server Room A", "PYRO-71010", "ASSIGNED", TODAY - timedelta(days=120), "DUE", "SRV", "A", 25, 50),
        Equipment("EQ-0010", "HVAC-L2-S", "감지기", "Smoke Detector - HVAC Level 2", "PYRO-72120", "ASSIGNED", TODAY - timedelta(days=80), "DUE", "L2", "HVAC", 50, 25),
        Equipment("EQ-0011", "LOB-EXT-A", "소화기", "Lobby Extinguisher A", "PYRO-73130", "ASSIGNED", TODAY - timedelta(days=30), "PASS", "L1", "LOB", 28, 75),
        Equipment("EQ-0012", "B2-EXT-04", "비상경보장치", "비상경보장치 #B2-04", "PYRO-74140", "PENDING", None, "DUE", "B2", "C", 55, 40),
    ]


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


@st.cache_data
def load_equipment() -> list[Equipment]:
    return _seed_equipment()


@st.cache_data
def load_tasks() -> list[InspectionTask]:
    return _seed_tasks()


def load_deficiencies() -> list[Deficiency]:
    """시드 + 세션에서 추가된 별지5 row를 합쳐 반환."""
    extra = st.session_state.get("added_deficiencies", [])
    return list(extra) + _seed_deficiencies()


def load_notices() -> list[Notice]:
    """시드 + 세션에서 추가된 통보서를 합쳐 반환."""
    extra = st.session_state.get("added_notices", [])
    return list(extra) + _seed_notices()


def load_malfunctions() -> list[Malfunction]:
    """시드 + 세션에서 추가된 오동작을 합쳐 반환."""
    extra = st.session_state.get("added_malfunctions", [])
    return list(extra) + _seed_malfunctions()


def add_deficiency(d: Deficiency) -> None:
    st.session_state.setdefault("added_deficiencies", []).insert(0, d)


def add_notice(n: Notice) -> None:
    st.session_state.setdefault("added_notices", []).insert(0, n)


def add_malfunction(m: Malfunction) -> None:
    st.session_state.setdefault("added_malfunctions", []).insert(0, m)


def next_notice_no(d: date) -> str:
    """같은 날짜 내 순번을 자동 증가시켜 YYYY-MM-DD-NN 형식 반환."""
    prefix = d.isoformat()
    existing = [n.notice_no for n in load_notices() if n.notice_no.startswith(prefix)]
    next_n = len(existing) + 1
    return f"{prefix}-{next_n:02d}"


# ---------- 집계 (KPI) ----------

def equipment_kpis() -> dict:
    eq = load_equipment()
    recent_threshold = TODAY - timedelta(hours=48)
    pending = sum(1 for e in eq if e.health_status in ("FAIL", "DUE"))
    assigned = sum(1 for e in eq if e.qr_status == "ASSIGNED")
    return {
        "total": len(eq),
        "new_this_month": 12,
        "recently_inspected": sum(1 for e in eq if e.last_inspection and e.last_inspection >= TODAY - timedelta(days=2)) + 430,
        "pending_issues": pending + 14,
        "qr_coverage": (assigned / len(eq)) * 100 if eq else 0,
    }


def task_kpis() -> dict:
    tasks = load_tasks()
    return {
        "total": 48,
        "overdue": sum(1 for t in tasks if t.status == "Overdue"),
        "in_progress": sum(1 for t in tasks if t.status == "In Progress") + 10,
        "completed": sum(1 for t in tasks if t.status == "Completed") + 28,
    }


def field_kpis() -> dict:
    tasks = load_tasks()
    defs = load_deficiencies()
    return {
        "inspections_today": sum(1 for t in tasks if t.due_date == TODAY) + 11,
        "pending_deficiencies": sum(1 for d in defs if d.resolution == "불가"),
    }
