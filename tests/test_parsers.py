from datetime import date

from gdweb_daily.gdweb import parse_detail_html, parse_listing_html


LIST_HTML = """
<ul class="thumnail"><li><div class="thumnail-box">
  <div class="img-box"><a href="./view.asp?Page=1&str_no=27271"><img></a></div>
  <div class="subject-box">
    <p class="subject"><a class="btn_link" val="27271">더가든피부과</a></p>
    <p class="date">26.07.17</p>
  </div>
</div></li></ul>
"""

DETAIL_HTML = """
<div class="view-area">
  <div class="title-box"><div class="txt">
    <p class="title">더가든피부과</p>
    <p class="url"><a href="https://thegardenclinic.co.kr/">바로가기</a></p>
  </div></div>
  <div class="content-info"><table>
    <tr><th>수상명</th><td>WINNER PRIZE</td></tr>
    <tr><th>선정증서번호</th><td>202607100001 (수상신청)</td></tr>
    <tr><th>등록일</th><td>2026년 07월 17일</td></tr>
    <tr><th>타겟층</th><td><span>여성</span>, <span>남성</span></td></tr>
    <tr><th>표현방법</th><td><span>모션그래픽</span>, <span>사진</span></td></tr>
    <tr><th>디자인 컨셉</th><td><span>모던한</span></td></tr>
    <tr><th>주색상</th><td><span>BROWN</span></td></tr>
    <tr><th>제작사</th><td><span>매스티지</span></td></tr>
  </table></div>
</div>
"""


def test_listing_parser() -> None:
    items = parse_listing_html(LIST_HTML, "https://www.gdweb.co.kr")
    assert len(items) == 1
    assert items[0].str_no == "27271"
    assert items[0].site_name == "더가든피부과"
    assert items[0].registered_date == date(2026, 7, 17)


def test_detail_parser() -> None:
    listing = parse_listing_html(LIST_HTML, "https://www.gdweb.co.kr")[0]
    detail = parse_detail_html(DETAIL_HTML, listing)
    assert detail.live_url == "https://thegardenclinic.co.kr/"
    assert detail.agency == "매스티지"
    assert detail.targets == ["여성", "남성"]
    assert detail.methods == ["모션그래픽", "사진"]
    assert detail.concepts == ["모던한"]
    assert detail.colors == ["BROWN"]

