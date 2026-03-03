Feature: Native text overlays and fonts
  In order to render text using built-in fonts
  As a developer
  I want native overlays, font listing, and overlay sequencing

  Scenario: Send overlay using a built-in font name
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I send text overlay "hello" using built-in font "font_4"
    Then a Draw/SendHttpText command should be sent
    And the text overlay font id should be 4

  Scenario: List built-in fonts
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I list built-in fonts
    Then the font list should include "font_4"

  Scenario: Upload sequence with overlays sends overlays after upload
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a native GIF sequence with 1 frames and speed 100ms
    When I upload the native sequence with 2 overlays
    Then 2 Draw/SendHttpText commands should be sent
    And the overlays should be sent after the upload
