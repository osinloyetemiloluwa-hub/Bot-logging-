import os
import sys

print("=== Environment Variables ===")
print(f"DATABASE_URL: {'Set' if os.getenv('DATABASE_URL') else 'Not Set'}")
print(f"DISCORD_TOKEN: {'Set' if os.getenv('DISCORD_TOKEN') else 'Not Set'}")
print(f"PORT: {os.getenv('PORT', 'Not Set')}")
print("=== Python Version ===")
print(sys.version)
print("=== Installed Packages ===")
import pkg_resources
for package in pkg_resources.working_set:
    print(f"{package.key}=={package.version}")
