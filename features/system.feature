Feature: System and channel controls
  In order to control core device settings
  As a developer
  I want system and channel commands plus a raw command fallback

  Scenario: Set brightness
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I set brightness to 80
    Then the last command should be "Channel/SetBrightness"
    And the last command payload should include "Brightness" 80

  Scenario: Select channel index
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I set channel index to 2
    Then the last command should be "Channel/SetIndex"
    And the last command payload should include "SelectIndex" 2

  Scenario: Raw command passthrough
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I send raw command "Device/SetHighLightMode" with "Mode" 1
    Then the last command should be "Device/SetHighLightMode"
    And the last command payload should include "Mode" 1
