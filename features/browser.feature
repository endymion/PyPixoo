Feature: Headless browser rendering
  In order to precompute frames from web content for the Pixoo 64
  As a developer
  I want to render URLs via Playwright and mix static and web frames

  @mock_browser
  Scenario: Static-only sequence
    Given a FrameRenderer with static sources only
    When I precompute frames
    Then the sequence should have 2 frames
    And each frame should have duration 100ms

  @mock_browser
  Scenario: Web-only sequence (mocked)
    Given a FrameRenderer with web source only at URL "http://example.com"
    And 3 timestamps 0.0 0.5 1.0
    And duration per frame 150ms
    When I precompute frames
    Then the sequence should have 3 frames
    And each frame should have duration 150ms

  @mock_browser
  Scenario: Mixed sequence (static, web, static)
    Given a FrameRenderer with mixed sources
    And web URL "http://example.com" with 1 timestamp and 200ms duration
    When I precompute frames
    Then the sequence should have 3 frames
    And frame order should be static web static

  @mock_browser
  Scenario: Persistent browser mode
    Given a FrameRenderer with web source in persistent mode
    And URL "http://example.com" and timestamps 0.0 1.0
    When I precompute frames
    Then the sequence should have 2 frames

  @mock_browser
  Scenario: Per-frame browser mode
    Given a FrameRenderer with web source in per_frame mode
    And URL "http://example.com" and timestamps 0.0 1.0
    When I precompute frames
    Then the sequence should have 2 frames

  @mock_browser
  Scenario: on_first_frame callback is called
    Given a FrameRenderer with web source only at URL "http://example.com"
    And 2 timestamps 0.0 1.0
    And an on_first_frame callback
    When I precompute frames
    Then on_first_frame should have been called

  @mock_browser
  Scenario: on_all_frames callback is called
    Given a FrameRenderer with static sources only
    And an on_all_frames callback
    When I precompute frames
    Then on_all_frames should have been called
