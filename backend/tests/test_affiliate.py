"""Affiliate link detection: only real tracking tokens count."""
from app import affiliate


def test_meesho_app_share_link_is_not_affiliate():
    """`utm_source=s_cc` is an ordinary share token, not a Creator Club link."""
    result = affiliate.check("https://www.meesho.com/s/p/9izlxr?utm_source=s_cc",
                             commission_percent=9, price=118)
    assert result["network"] == "meesho"
    assert result["affiliate"] is False
    assert "No affiliate tracking found for Meesho" in result["issues"]


def test_meesho_creator_club_aff_id_is_affiliate():
    result = affiliate.check(
        "https://www.meesho.com/s/p/9izlxr?aff_id=12345&sub_id=shorts",
        commission_percent=9, price=118,
    )
    assert result["network"] == "meesho"
    assert result["affiliate"] is True
    assert result["issues"] == []


def test_meesho_creator_club_sub_id_is_affiliate():
    result = affiliate.check("https://www.meesho.com/s/p/9izlxr?sub_id=abc123",
                             commission_percent=9, price=118)
    assert result["affiliate"] is True


def test_meesho_creator_club_af_invite_path_is_affiliate():
    """The real Creator Club link puts the creator id in the path."""
    url = ("https://www.meesho.com/af_invite/416304105:youtube_long_form:14671745"
           "?p_id=576090063&ext_id=9izlxr&utm_source=youtube_long_form")
    result = affiliate.check(url, commission_percent=0.5, price=118)
    assert result["network"] == "meesho"
    assert result["affiliate"] is True
    assert result["issues"] == []
    assert affiliate.is_affiliate_link(url) is True


def test_meesho_plain_short_link_is_not_affiliate():
    assert affiliate.is_affiliate_link("https://meesho.me/9izlxr") is False


def test_demo_link_is_never_affiliate():
    result = affiliate.check(
        "https://www.meesho.com/s/p/9izlxr?aff_id=12345",
        demo=True, commission_percent=9, price=118,
    )
    assert result["affiliate"] is False
    assert "Sample product - no real commission link yet" in result["issues"]


def test_wrapper_network_is_affiliate():
    result = affiliate.check("https://earnkaro.com/xyz", commission_percent=5, price=99)
    assert result["network"] == "earnkaro"
    assert result["wrapper"] is True
    assert result["affiliate"] is True
