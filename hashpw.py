"""Generate a bcrypt password hash for use in MEGAQUEUE_PASSWORD_HASH config."""
import getpass
import bcrypt

password = getpass.getpass("Enter password: ")
hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
print(f"\nSet this as your MEGAQUEUE_PASSWORD_HASH:\n{hashed.decode('utf-8')}")
