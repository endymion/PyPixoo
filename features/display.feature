Feature: Display control
  In order to show content on my Pixoo 64
  As a developer
  I want to connect, draw, and push to the device

  Scenario: Connect and push a fill
    Given a Pixoo at IP "192.168.0.37"
    When I connect
    And I fill with RGB 255 0 68
    And I push
    Then no error should occur
    And the buffer should be 64 by 64
    And the buffer at 0 0 should be RGB 255 0 68
