from datetime import timedelta
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token, decode_refresh_token, create_refresh_token

def test_password_unicode_long_and_wrong():
    password='தமிழ்' * 20
    hashed=hash_password(password)
    assert verify_password(password,hashed)
    assert not verify_password('wrong',hashed)
    assert not verify_password(password,'invalid-hash')

def test_token_expiry_type_and_tampering():
    access=create_access_token({'sub':'user','sid':'session'})
    assert decode_access_token(access)['sub']=='user'
    assert decode_refresh_token(access) is None
    assert decode_access_token(create_refresh_token({'sub':'user'})) is None
    assert decode_access_token(access+'broken') is None
    assert decode_access_token(create_access_token({'sub':'user'},timedelta(seconds=-1))) is None

def test_exception_contract():
    from app.core.exceptions import NotFoundException
    exc=NotFoundException('Missing')
    assert exc.status_code==404
    assert exc.to_dict()['success'] is False
