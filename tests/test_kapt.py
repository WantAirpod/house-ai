from home_decision_ai.collectors.kapt import parse_basic_info_xml
from home_decision_ai.collectors.kapt import parse_complex_list_xml
from home_decision_ai.collectors.kapt import parse_detail_info_xml


def test_parse_complex_list_xml() -> None:
    xml = """
    <response>
      <body>
        <items>
          <item>
            <kaptCode>A100000001</kaptCode>
            <kaptName>테스트아파트</kaptName>
          </item>
        </items>
      </body>
    </response>
    """

    complexes = parse_complex_list_xml(xml)

    assert len(complexes) == 1
    assert complexes[0].kapt_code == "A100000001"
    assert complexes[0].name == "테스트아파트"


def test_parse_basic_info_xml() -> None:
    xml = """
    <response>
      <body>
        <item>
          <kaptCode>A100000001</kaptCode>
          <kaptName>테스트아파트</kaptName>
          <kaptAddr>경기도 용인시 수지구 테스트동 1</kaptAddr>
          <doroJuso>경기도 용인시 수지구 테스트로 1</doroJuso>
          <codeSaleNm>분양</codeSaleNm>
          <codeHeatNm>지역난방</codeHeatNm>
          <kaptTarea>123456.78</kaptTarea>
          <kaptDongCnt>12</kaptDongCnt>
          <kaptdaCnt>550</kaptdaCnt>
          <kaptBcompany>테스트건설</kaptBcompany>
          <kaptAcompany>테스트시행</kaptAcompany>
          <codeAptNm>아파트</codeAptNm>
          <codeHallNm>계단식</codeHallNm>
          <kaptUsedate>20190101</kaptUsedate>
          <kaptMarea>100000.5</kaptMarea>
          <kaptMparea_60>120</kaptMparea_60>
          <kaptMparea_85>430</kaptMparea_85>
          <kaptMparea_135>0</kaptMparea_135>
          <kaptMparea_136>0</kaptMparea_136>
          <privArea>40000.3</privArea>
          <bjdCode>4146510100</bjdCode>
        </item>
      </body>
    </response>
    """

    info = parse_basic_info_xml(xml)

    assert info is not None
    assert info.name == "테스트아파트"
    assert info.household_count == 550
    assert info.building_count == 12
    assert info.complex_type == "아파트"
    assert info.approval_date == "20190101"
    assert info.households_60_to_85 == 430


def test_parse_detail_info_xml() -> None:
    xml = """
    <response>
      <body>
        <item>
          <kaptCode>A100000001</kaptCode>
          <kaptName>테스트아파트</kaptName>
          <codeStr>철근콘크리트구조</codeStr>
          <kaptdEcnt>20</kaptdEcnt>
          <kaptdPcnt>100</kaptdPcnt>
          <kaptdPcntu>500</kaptdPcntu>
          <welfareFacility>관리사무소, 노인정</welfareFacility>
          <kaptdWtimebus>5분이내</kaptdWtimebus>
          <subwayLine>신분당선</subwayLine>
          <subwayStation>성복</subwayStation>
          <kaptdWtimesub>10분이내</kaptdWtimesub>
          <convenientFacility>백화점</convenientFacility>
          <educationFacility>초등학교</educationFacility>
          <kaptdCccnt>120</kaptdCccnt>
        </item>
      </body>
    </response>
    """

    info = parse_detail_info_xml(xml)

    assert info is not None
    assert info.subway_line == "신분당선"
    assert info.subway_station == "성복"
    assert info.subway_distance == "10분이내"
    assert info.parking_underground_count == 500
    assert info.cctv_count == 120
