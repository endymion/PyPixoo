Feature: Apps and tools commands
  In order to use built-in tools and overlays
  As a developer
  I want tool commands and display list support

  Scenario: Set countdown timer tool
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I set countdown timer to 1 minutes 0 seconds with status 1
    Then the last command should be "Tools/SetTimer"
    And the last command payload should include "Minute" 1
    And the last command payload should include "Second" 0
    And the last command payload should include "Status" 1

  Scenario: Send display list with one item
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I send display list with one item
    Then the last command should be "Draw/SendHttpItemList"

  Scenario: Play buzzer
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I play buzzer with active 500 off 500 total 3000
    Then the last command should be "Device/PlayBuzzer"
