Feature: pixooclock adaptive default palette
  In order to keep the clock visually coherent through day and night
  As a user running pixooclock with defaults
  I want automatic band selection based on local daylight conditions

  # Planning scenarios (implemented in follow-up stories):
  # 1) Auto + daytime picks day band (sand)
  # 2) Auto + nighttime picks night band (bronze)
  # 3) Explicit --band override bypasses adaptive logic
  # 4) No location uses timezone seasonal fallback
  # 5) Runtime boundary crossing switches band without restart
  # 6) --demo mode bypasses adaptive logic
