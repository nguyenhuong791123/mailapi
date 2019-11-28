
# -*- coding: UTF-8 -*-
import json
import base64
import re
import smtplib
from validate_email import validate_email

def is_empty(val):
    return (val is None or len(val) <= 0)

def is_exist(obj, key):
    return key in obj.keys()

def is_mail(val):
    val = re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', val)
    return (val is not None)

def is_valid(val):
    return (validate_email(val) == True)

def is_verify(val):
    return (validate_email(val, verify=True) == True)

def is_valid_mx(val):
    return (validate_email(val, check_mx=True) == True)

def convert_b64_string_to_file(s, outfile_path):
    with open(outfile_path, "wb") as f:
        f.write(base64.b64decode(s))

def is_json(obj):
    keys = obj.keys()
    try:
        if keys is None:
            data = json.load(obj)
            keys = data.keys()
            # print(data)
    except json.JSONDecodeError as e:
        print('JSONDecodeError: ', e)
    # print(keys)
    return (keys is not None and len(keys) > 0)

# def is_mail_server_mx(val):
#     if is_empty(val):
#         return None
#     # if val.find('@') > -1:
#     #     val = val[(val.find('@')+1):len(val)]
#     domain = re.search("(.*)(@)(.*)", val).group(3)
#     records = dns.resolver.query(domain, 'MX')
#     mx = records[0].exchange
#     return str(mx)

# def is_account_verify(fm, tm):
#     mx = is_mail_server_mx(tm)
#     print(mx)
#     if is_empty(mx) == True:
#         return False

#     host = socket.gethostname()
#     server = smtplib.SMTP(timeout=5)
#     server.set_debuglevel(0)
#     try:
#         server.connect(mx)
#         server.helo(host)
#         server.mail(fm)
#         code, message = server.rcpt(str(tm))
#         server.quit()
#         if code == 250:
#             print('Address exists') # 250 OK
#             return True
#         else:
#             print('Address does not exists')
#             return False
#     except Exception as e:
#         print(e)
#         return False
