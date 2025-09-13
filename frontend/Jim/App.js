import { StatusBar } from "expo-status-bar";
import React from "react";
import { StyleSheet, Text, View } from "react-native";

// export default function App() {
//   return (
//     <View style={styles.container}>
//       <Text>Open up App.js to start working on your app!</Text>
//       <StatusBar style="auto" />
//     </View>
//   );
// }

import { Camera } from "expo-camera";
import { Audio } from "expo-av";
import { useEffect, useState } from "react";
import { useRef } from "react";
import { Button } from "react-native";

export default function App() {
  const [hasCameraPermission, setHasCameraPermission] = useState(null);
  const [hasAudioPermission, setHasAudioPermission] = useState(null);

  const [type, setType] = useState(Camera.Constants.Type.back);
  const cameraRef = useRef(null);

  useEffect(() => {
    (async () => {
      const cameraStatus = await Camera.requestCameraPermissionsAsync();
      setHasCameraPermission(cameraStatus.status === "granted");

      const audioStatus = await Audio.requestPermissionsAsync();
      setHasAudioPermission(audioStatus.status === "granted");
    })();
  }, []);

  if (hasCameraPermission === null || hasAudioPermission === null) {
    return (
      <View style={styles.container}>
        <Text>No access to camera or microphone</Text>
      </View>
    ); // Or a loading spinner
  }

  if (!hasCameraPermission || !hasAudioPermission) {
    return (
      <View style={styles.container}>
        <Text>No access to camera or microphone</Text>
      </View>
    );
  }

  // return (
  //   <View style={styles.container}>
  //     <Text>Open up App.js to start working on your app!</Text>
  //   </View>
  // );

  return (
    <View style={styles.container}>
      <Camera style={styles.camera} type={type} ref={cameraRef} />
      <Button
        title="Flip Camera"
        onPress={() =>
          setType(
            type === Camera.Constants.Type.back
              ? Camera.Constants.Type.front
              : Camera.Constants.Type.back
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  camera: { flex: 1 },
  // container: {
  //   flex: 1,
  //   backgroundColor: "#fff",
  //   alignItems: "center",
  //   justifyContent: "center",
  // },
});
