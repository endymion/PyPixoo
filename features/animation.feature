Feature: Animation sequences
  In order to animate content on the Pixoo 64
  As a developer
  I want to play sequences of frames with timing and blend controls

  Scenario: Play 2-frame sequence once
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 2-frame sequence with 100ms duration each
    When I play the animation async
    And I wait for the animation to complete
    Then the animation should have pushed 2 frames

  Scenario: Blend mode opaque sends frame as-is
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 1-frame sequence with solid color 255 0 0 and duration 0
    And blend mode opaque
    When I play the animation async
    And I wait for the animation to complete
    Then the first pushed frame should be solid RGB 255 0 0

  Scenario: Blend mode transparent composites over background
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 1-frame sequence with transparent center and magenta background
    When I play the animation async with transparent blend
    And I wait for the animation to complete
    Then the first pushed frame should have magenta at center

  Scenario: End on last frame
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 2-frame sequence with different colors
    And end on last frame
    When I play the animation async
    And I wait for the animation to complete
    Then the last pushed frame should match the last frame of the sequence

  Scenario: End on blank
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 1-frame sequence with solid color 0 255 0 and duration 0
    And end on blank with background color 0 0 255
    When I play the animation async
    And I wait for the animation to complete
    Then the last pushed frame should be solid RGB 0 0 255

  Scenario: Loop 2 times
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 2-frame sequence with 0ms duration each
    And loop 2 times
    When I play the animation async
    And I wait for the animation to complete
    Then the animation should have pushed 4 frames

  Scenario: Transparent without background raises
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 1-frame sequence with solid color 255 0 0 and duration 0
    When I play the animation async with transparent blend and no background
    Then an animation ValueError should occur

  Scenario: on_finished callback is called when animation completes
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 1-frame sequence with solid color 0 0 0 and duration 0
    And an on_finished callback
    When I play the animation async
    And I wait for the animation to complete
    Then the on_finished callback should have been called

  Scenario: on_loop callback is called for each loop
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 2-frame sequence with 0ms duration each
    And loop 2 times
    And an on_loop callback
    When I play the animation async
    And I wait for the animation to complete
    Then the on_loop callback should have been called 2 times

  Scenario: Play async when already playing raises
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a 1-frame sequence with 0ms duration and loop forever
    When I play the animation async
    And I wait a short time
    When I play the animation async again
    Then an animation RuntimeError should occur
