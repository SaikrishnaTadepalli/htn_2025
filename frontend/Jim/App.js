import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { CameraView, useCameraPermissions } from "expo-camera";
import { Audio } from "expo-av";
import { useEffect, useState } from "react";
import { useRef } from "react";
import { Button } from "react-native";
import { useAudioRecording } from "./hooks/useAudioRecording";
import { useAudioPlayback } from "./hooks/useAudioPlayback";

export default function App() {
  const [permission, requestPermission] = useCameraPermissions();
  const [hasAudioPermission, setHasAudioPermission] = useState(null);

  const [facing, setFacing] = useState("back");
  const cameraRef = useRef(null);

  // Audio hooks
  const {
    isRecording,
    recordingState,
    error: recordingError,
    formattedDuration,
    chunksRecorded,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
  } = useAudioRecording();

  const {
    isPlaying,
    playbackState,
    error: playbackError,
    volume,
    bufferedChunks,
    queueLength,
    startPlayback,
    stopPlayback,
    pausePlayback,
    resumePlayback,
    adjustVolume,
  } = useAudioPlayback();

  useEffect(() => {
    (async () => {
      const audioStatus = await Audio.requestPermissionsAsync();
      setHasAudioPermission(audioStatus.status === "granted");
    })();
  }, []);

  if (!permission) {
    return (
      <View style={styles.container}>
        <Text>Loading camera permissions...</Text>
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.container}>
        <Text style={{ textAlign: "center" }}>
          We need your permission to show the camera
        </Text>
        <Button onPress={requestPermission} title="grant permission" />
      </View>
    );
  }

  if (hasAudioPermission === null) {
    return (
      <View style={styles.container}>
        <Text>Loading audio permissions...</Text>
      </View>
    );
  }

  if (!hasAudioPermission) {
    return (
      <View style={styles.container}>
        <Text>No access to microphone</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView style={styles.camera} facing={facing} ref={cameraRef}>
        <View style={styles.buttonContainer}>
          <Button
            title="Flip Camera"
            onPress={() => setFacing(facing === "back" ? "front" : "back")}
          />
        </View>

        {/* Audio Controls Overlay */}
        <View style={styles.audioControls}>
          {/* Recording Status */}
          <View style={styles.statusContainer}>
            <Text style={styles.statusText}>
              Recording: {recordingState} {isRecording && `(${formattedDuration}, ${chunksRecorded} chunks)`}
            </Text>
            <Text style={styles.statusText}>
              Playback: {playbackState} {bufferedChunks > 0 && `(Buffered: ${bufferedChunks})`}
            </Text>
          </View>

          {/* Recording Controls */}
          <View style={styles.controlRow}>
            <Button
              title={isRecording ? "Stop Rec" : "Start Rec"}
              onPress={isRecording ? stopRecording : startRecording}
              color={isRecording ? "#ff4444" : "#44ff44"}
            />
            {isRecording && (
              <Button
                title="Pause Rec"
                onPress={pauseRecording}
                color="#ffaa44"
              />
            )}
          </View>

          {/* Playback Controls */}
          <View style={styles.controlRow}>
            <Button
              title="Test Playback"
              onPress={startPlayback}
              color="#4444ff"
            />
            <Button
              title={isPlaying ? "Stop Play" : "Resume Play"}
              onPress={isPlaying ? stopPlayback : resumePlayback}
              color={isPlaying ? "#ff4444" : "#44ff44"}
            />
          </View>

          {/* Error Display */}
          {(recordingError || playbackError) && (
            <Text style={styles.errorText}>
              Error: {recordingError?.message || playbackError?.message}
            </Text>
          )}
        </View>
      </CameraView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  camera: { flex: 1 },
  buttonContainer: {
    flex: 1,
    flexDirection: "row",
    backgroundColor: "transparent",
    margin: 64,
  },
  audioControls: {
    position: "absolute",
    bottom: 120,
    left: 20,
    right: 20,
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    borderRadius: 10,
    padding: 15,
  },
  statusContainer: {
    marginBottom: 10,
  },
  statusText: {
    color: "white",
    fontSize: 12,
    marginBottom: 2,
  },
  controlRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginBottom: 10,
  },
  errorText: {
    color: "#ff4444",
    fontSize: 12,
    textAlign: "center",
    marginTop: 5,
  },
});
