from home_decision_ai.collectors.molit_rtms import parse_rtms_xml


def test_parse_rtms_xml() -> None:
    xml = """
    <response>
      <body>
        <items>
          <item>
            <아파트>테스트아파트</아파트>
            <전용면적>84.91</전용면적>
            <거래금액>105,000</거래금액>
            <층>12</층>
            <일>24</일>
            <건축년도>2019</건축년도>
          </item>
        </items>
      </body>
    </response>
    """

    trades = parse_rtms_xml(xml, lawd_cd="41465", deal_ym="202606")

    assert len(trades) == 1
    assert trades[0].apartment_name == "테스트아파트"
    assert trades[0].area_m2 == 84.91
    assert trades[0].price_krw == 1_050_000_000
