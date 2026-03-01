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

  Scenario: Buffer get_pixel raises IndexError for out-of-range coordinates
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And I fill with RGB 0 0 0
    When I get the buffer pixel at 64 0
    Then an IndexError should occur

  @mock_validate_fail
  Scenario: Connect returns False when device validation request raises RequestException
    Given a Pixoo at IP "192.168.0.37"
    When I connect
    Then connection should be unsuccessful

  @mock_load_counter_fail
  Scenario: Connect raises when device load counter returns error
    Given a Pixoo at IP "192.168.0.37"
    When I connect
    Then a RuntimeError should occur on connect

  @mock_push_fail
  Scenario: Push raises when device returns error
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And I fill with RGB 255 0 0
    When I push
    Then a RuntimeError should occur on push

  Scenario: Load small image and resize to buffer
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I load image "features/fixtures/small_32x32.png"
    Then no load error should occur
    And the buffer should be 64 by 64
    And the buffer at 0 0 should be RGB 255 0 255

  Scenario: Load gradient image and push
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I load image "features/fixtures/gradient_magenta_to_black.png"
    Then no load error should occur
    And the buffer at 0 0 should be RGB 255 0 255
    And the buffer at 63 63 should be RGB 0 0 0
    When I push
    Then no error should occur

  @real_device
  Scenario: Load gradient and push to real device
    Given a Pixoo at IP "192.168.0.37"
    When I connect
    And I load image "features/fixtures/gradient_magenta_to_black.png"
    And I push
    Then no error should occur
