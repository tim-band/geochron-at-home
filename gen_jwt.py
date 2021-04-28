#!/usr/bin/env python3
# Open production.env (or .env or wherever you keep your environment
# variables) and delete the lines beginning JWT_PUBLIC_KEY and
# JWT_PRIVATE_KEY. Now run:
# ./gen_jwt.py >> production.env
# to add new ones back in.
import rsa
(pubkey, prikey) = rsa.newkeys(4096)
pub = pubkey.save_pkcs1().decode('ascii').replace('\n', '')
pri = prikey.save_pkcs1().decode('ascii').replace('\n', '')
print("JWT_PUBLIC_KEY={0}\nJWT_PRIVATE_KEY={1}".format(pub, pri))
