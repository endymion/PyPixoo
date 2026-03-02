Feature: Native GIF sequencing and playback
  In order to align with Pixoo native capabilities
  As a developer
  I want to upload sequences, play native GIF sources, and orchestrate cycles

  Scenario: Upload sequence frame-by-frame with stable PicID
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a native GIF sequence with 2 frames and speed 120ms
    When I upload the native sequence in mode "frame_by_frame"
    Then 2 Draw/SendHttpGif commands should be sent
    And all uploaded frames should use the same PicID
    And uploaded frame offsets should be 0,1
    And all uploaded frames should have PicNum 2
    And all uploaded frames should have PicSpeed 120

  Scenario: Upload sequence via CommandList with chunking
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a native GIF sequence with 90 frames and speed 50ms
    When I upload the native sequence in mode "command_list" with chunk size 40
    Then 3 Draw/CommandList commands should be sent
    And command list chunk sizes should be 40,40,10
    And nested uploaded frame offsets should span 0 through 89
    And all nested uploaded frames should use the same PicID

  Scenario: Get and reset HTTP GIF ID
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I query the HTTP GIF ID
    Then the returned HTTP GIF ID should be 1
    When I reset the HTTP GIF ID
    Then a Draw/ResetHttpGifId command should be sent

  Scenario: Play GIF from URL
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I play GIF source type "url" with value "https://example.com/a.gif"
    Then the last Device/PlayTFGif command should use FileType 2

  Scenario: Play GIF from TF file
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I play GIF source type "tf_file" with value "divoom_gif/1.gif"
    Then the last Device/PlayTFGif command should use FileType 0

  Scenario: Play GIF from TF directory
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    When I play GIF source type "tf_directory" with value "divoom_gif/"
    Then the last Device/PlayTFGif command should use FileType 1

  Scenario: Send and clear text overlay for HttpGif context
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And a native GIF sequence with 1 frames and speed 100ms
    And I upload the native sequence in mode "frame_by_frame"
    When I send text overlay "hello, pixoo"
    Then a Draw/SendHttpText command should be sent
    When I clear the text overlay
    Then a Draw/ClearHttpText command should be sent

  Scenario: Text overlay is blocked after PlayTFGif
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And I play GIF source type "url" with value "https://example.com/a.gif"
    When I send text overlay "not allowed"
    Then a native ValueError should occur

  Scenario: Cycle items execute in configured order
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And cycle items of sequence, url gif, and tf file gif
    And cycle callbacks are registered
    When I start cycle with loop count 1
    And I wait for cycle completion
    Then cycle on_item callback order should be 0,1,2
    And cycle on_loop callback counts should be 1

  Scenario: Cycle handle can stop an infinite cycle
    Given a Pixoo at IP "192.168.0.37"
    And I connect
    And cycle items containing one url gif
    When I start cycle with infinite loop
    And I wait briefly
    And I stop the running cycle
    Then the cycle should not be running
