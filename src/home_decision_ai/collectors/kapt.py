from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree


KAPT_LIST_URL = "http://apis.data.go.kr/1611000/AptListService/getLegaldongAptList"
KAPT_BASIC_INFO_URL = "http://apis.data.go.kr/1611000/AptBasisInfoService/getAphusBassInfo"
KAPT_DETAIL_INFO_URL = "http://apis.data.go.kr/1611000/AptBasisInfoService/getAphusDtlInfo"


@dataclass(frozen=True)
class KaptComplex:
    kapt_code: str
    name: str


@dataclass(frozen=True)
class KaptBasicInfo:
    kapt_code: str
    name: str
    legal_address: str | None
    road_address: str | None
    sale_type: str | None
    heating_type: str | None
    total_area_m2: float | None
    building_count: int | None
    household_count: int | None
    construction_company: str | None
    developer: str | None
    complex_type: str | None
    hallway_type: str | None
    approval_date: str | None
    management_area_m2: float | None
    households_under_60: int | None
    households_60_to_85: int | None
    households_85_to_135: int | None
    households_over_135: int | None
    private_area_total_m2: float | None
    bjd_code: str | None


@dataclass(frozen=True)
class KaptDetailInfo:
    kapt_code: str
    name: str
    structure: str | None
    elevator_count: int | None
    parking_ground_count: int | None
    parking_underground_count: int | None
    welfare_facility: str | None
    bus_stop_distance: str | None
    subway_line: str | None
    subway_station: str | None
    subway_distance: str | None
    convenient_facility: str | None
    education_facility: str | None
    cctv_count: int | None


def parse_int(raw_value: str | None) -> int | None:
    if not raw_value or not raw_value.strip():
        return None
    normalized = raw_value.replace(",", "").strip()
    try:
        return int(float(normalized))
    except ValueError:
        return None


def parse_float(raw_value: str | None) -> float | None:
    if not raw_value or not raw_value.strip():
        return None
    normalized = raw_value.replace(",", "").strip()
    try:
        return float(normalized)
    except ValueError:
        return None


def child_text(item: ElementTree.Element, *names: str) -> str | None:
    for name in names:
        found = item.find(name)
        if found is not None and found.text and found.text.strip():
            return found.text.strip()
    return None


def first_item(xml_text: str) -> ElementTree.Element | None:
    root = ElementTree.fromstring(xml_text)
    return root.find(".//item")


def parse_complex_list_xml(xml_text: str) -> list[KaptComplex]:
    root = ElementTree.fromstring(xml_text)
    complexes: list[KaptComplex] = []
    for item in root.findall(".//item"):
        kapt_code = child_text(item, "kaptCode", "kaptcode")
        name = child_text(item, "kaptName", "kaptname")
        if kapt_code and name:
            complexes.append(KaptComplex(kapt_code=kapt_code, name=name))
    return complexes


def parse_basic_info_xml(xml_text: str) -> KaptBasicInfo | None:
    item = first_item(xml_text)
    if item is None:
        return None

    kapt_code = child_text(item, "kaptCode", "kaptcode") or ""
    name = child_text(item, "kaptName", "kaptname") or ""
    if not kapt_code and not name:
        return None

    return KaptBasicInfo(
        kapt_code=kapt_code,
        name=name,
        legal_address=child_text(item, "kaptAddr", "kaptaddr"),
        road_address=child_text(item, "doroJuso", "dorojuso"),
        sale_type=child_text(item, "codeSaleNm", "codesalenm"),
        heating_type=child_text(item, "codeHeatNm", "codeheatnm"),
        total_area_m2=parse_float(child_text(item, "kaptTarea", "kapttarea")),
        building_count=parse_int(child_text(item, "kaptDongCnt", "kaptdongcnt")),
        household_count=parse_int(child_text(item, "kaptdaCnt", "kaptdacnt")),
        construction_company=child_text(item, "kaptBcompany", "kaptbcompany"),
        developer=child_text(item, "kaptAcompany", "kaptacompany"),
        complex_type=child_text(item, "codeAptNm", "codeaptnm"),
        hallway_type=child_text(item, "codeHallNm", "codehallnm"),
        approval_date=child_text(item, "kaptUsedate", "kaptusedate"),
        management_area_m2=parse_float(child_text(item, "kaptMarea", "kaptmarea")),
        households_under_60=parse_int(child_text(item, "kaptMparea_60", "kaptmparea_60")),
        households_60_to_85=parse_int(child_text(item, "kaptMparea_85", "kaptmparea_85")),
        households_85_to_135=parse_int(child_text(item, "kaptMparea_135", "kaptmparea_135")),
        households_over_135=parse_int(child_text(item, "kaptMparea_136", "kaptmparea_136")),
        private_area_total_m2=parse_float(child_text(item, "privArea", "privarea")),
        bjd_code=child_text(item, "bjdCode", "bjdcode"),
    )


def parse_detail_info_xml(xml_text: str) -> KaptDetailInfo | None:
    item = first_item(xml_text)
    if item is None:
        return None

    kapt_code = child_text(item, "kaptCode", "kaptcode") or ""
    name = child_text(item, "kaptName", "kaptname") or ""
    if not kapt_code and not name:
        return None

    return KaptDetailInfo(
        kapt_code=kapt_code,
        name=name,
        structure=child_text(item, "codeStr", "codestr"),
        elevator_count=parse_int(child_text(item, "kaptdEcnt", "kaptdEcnt")),
        parking_ground_count=parse_int(child_text(item, "kaptdPcnt", "kaptdpcnt")),
        parking_underground_count=parse_int(child_text(item, "kaptdPcntu", "kaptdpcntu")),
        welfare_facility=child_text(item, "welfareFacility", "welfarefacility"),
        bus_stop_distance=child_text(item, "kaptdWtimebus", "kaptdwtimebus"),
        subway_line=child_text(item, "subwayLine", "subwayline"),
        subway_station=child_text(item, "subwayStation", "subwaystation"),
        subway_distance=child_text(item, "kaptdWtimesub", "kaptdwtimesub"),
        convenient_facility=child_text(item, "convenientFacility", "convenientfacility"),
        education_facility=child_text(item, "educationFacility", "educationfacility"),
        cctv_count=parse_int(child_text(item, "kaptdCccnt", "kaptdcccnt")),
    )


def fetch_complexes_by_legal_dong(
    *,
    service_key: str,
    bjd_code: str,
    rows: int = 100,
) -> list[KaptComplex]:
    query = urlencode({"serviceKey": service_key, "bjdCode": bjd_code, "numOfRows": rows})
    with urlopen(f"{KAPT_LIST_URL}?{query}", timeout=30) as response:
        xml_text = response.read().decode("utf-8")
    return parse_complex_list_xml(xml_text)


def fetch_basic_info(*, service_key: str, kapt_code: str) -> KaptBasicInfo | None:
    query = urlencode({"serviceKey": service_key, "kaptCode": kapt_code})
    with urlopen(f"{KAPT_BASIC_INFO_URL}?{query}", timeout=30) as response:
        xml_text = response.read().decode("utf-8")
    return parse_basic_info_xml(xml_text)


def fetch_detail_info(*, service_key: str, kapt_code: str) -> KaptDetailInfo | None:
    query = urlencode({"serviceKey": service_key, "kaptCode": kapt_code})
    with urlopen(f"{KAPT_DETAIL_INFO_URL}?{query}", timeout=30) as response:
        xml_text = response.read().decode("utf-8")
    return parse_detail_info_xml(xml_text)
