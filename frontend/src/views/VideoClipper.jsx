import { useState, useRef, useEffect, useCallback } from "react";

export default function VideoClipper() {
  const [videoFile, setVideoFile] = useState(null);
  const [intervals, setIntervals] = useState([]);
  const [videoUrl, setVideoUrl] = useState(null);
  const [currentMarks, setCurrentMarks] = useState([]);
  const videoRef = useRef(null);
  const currentMarksRef = useRef([]);
  const [audioFile, setAudioFile] = useState(null);

  const getTotalSelectedSeconds = () => {
    return intervals.reduce((total, [start, end]) => total + (end - start), 0);
  };

  useEffect(() => {
    currentMarksRef.current = currentMarks;
  }, [currentMarks]);

  const handleAudioUpload = (e) => {
    setAudioFile(e.target.files[0]);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    setVideoFile(file);
    setVideoUrl(URL.createObjectURL(file));
  };

  useEffect(() => {
    currentMarksRef.current = currentMarks;
  }, [currentMarks]);

  const markTime = useCallback(() => {
    if (videoRef.current) {
      const newTime = videoRef.current.currentTime;
      setCurrentMarks(prevMarks => {
        const updatedMarks = prevMarks.length < 2 && (prevMarks.length === 0 || newTime > prevMarks[prevMarks.length - 1])
          ? [...prevMarks, newTime]
          : [newTime];
        currentMarksRef.current = updatedMarks;
        return updatedMarks;
      });
    }
  }, []);

  const addInterval = useCallback(() => {
    console.log("addInterval called", currentMarksRef.current);
    if (currentMarksRef.current.length >= 2) {
      setIntervals(prevIntervals => [...prevIntervals, [currentMarksRef.current[0], currentMarksRef.current[1]]]);
      setCurrentMarks([]);
    } else {
      console.log("Not enough marks to create an interval");
    }
  }, []);


  useEffect(() => {
    const handleKeyPress = (event) => {
      console.log("Key pressed:", event.key);
      if (event.key === 'x') {
        markTime();
      } else if (event.key === 'c') {
        console.log("Attempting to add interval");
        addInterval();
      }
    };

    window.addEventListener('keydown', handleKeyPress);

    return () => {
      window.removeEventListener('keydown', handleKeyPress);
    };
  }, [markTime, addInterval]);

  const removeInterval = (index) => {
    setIntervals(intervals.filter((_, i) => i !== index));
  };

  const downloadClippedVideo = async () => {
    if (!videoFile || intervals.length === 0) {
      alert("Please upload a video and add at least one interval.");
      return;
    }

    const formData = new FormData();
    formData.append("video", videoFile);
    formData.append("intervals", intervals.map(interval => interval.join('-')).join(','));
    if (audioFile) {
      formData.append("audio", audioFile);
    }

    try {
      const response = await fetch("http://localhost:8000/clip-video/", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.style.display = "none";
        a.href = url;
        a.download = "clipped_video_with_audio.mp4";
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
      } else {
        const errorText = await response.text();
        console.error("Error:", errorText);
        alert("Error clipping video. Please try again.");
      }
    } catch (error) {
      console.error("Error:", error);
      alert("Error clipping video. Please try again.");
    }
  };

  const saveIntervalsToFile = () => {
    const blob = new Blob([JSON.stringify(intervals)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "intervals.json";
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleLoadIntervals = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const loadedIntervals = JSON.parse(event.target.result);
          if (Array.isArray(loadedIntervals)) {
            setIntervals(loadedIntervals);
          } else {
            alert("Invalid file format");
          }
        } catch (error) {
          alert("Error loading intervals");
        }
      };
      reader.readAsText(file);
    }
  };

  return (
    <div className="p-4 max-w-3xl mx-auto">
      <div>
      <span>Video:</span>
      <input type="file" accept="video/*" onChange={handleFileUpload} className="mb-4" />
      <span>Audio:</span>
      <input type="file" accept="audio/*" onChange={handleAudioUpload} className="mb-4" />
      <span>Intervals:</span>
      <input type="file" accept="application/json" onChange={handleLoadIntervals} className="mb-4" />
      </div>
      {audioFile && <p>Audio file uploaded: {audioFile.name}</p>}
      {videoFile && (
        <div>
          <div className="flex justify-center">
            <div className="relative w-full max-w-3xl">
              <video ref={videoRef} src={videoUrl} controls className="w-full" />
              <div className="absolute bottom-0 left-0 right-0 h-2 bg-gray-200">
                {currentMarks.map((mark, index) => (
                  <div
                    key={index}
                    className="absolute h-full bg-red-500"
                    style={{ left: `${(mark / videoRef.current?.duration) * 100}%`, width: '2px' }}
                  ></div>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 flex justify-between">
            <button onClick={markTime} className="bg-blue-500 text-white p-2">Mark Time (X)</button>
            <button onClick={addInterval} className="bg-green-500 text-white p-2">Add Interval (C)</button>
            <button onClick={saveIntervalsToFile} className="bg-yellow-500 text-white p-2">Save Intervals</button>
            <button onClick={downloadClippedVideo} className="bg-gray-500 text-white p-2">Download Clipped Video</button>
          </div>
            <div className="mt-4">
              <h3 className="font-bold">Current Marks:</h3>
              {currentMarks.length > 0 ? (
                <ul>
                  {currentMarks.map((mark, index) => (
                    <li key={index}>{mark.toFixed(3)}s</li>
                  ))}
                </ul>
              ) : (
                <span>None</span>
              )}
            </div>
          <div className="mt-4">
            <h3 className="font-bold">Total Selected Time:</h3>
            <span>{getTotalSelectedSeconds().toFixed(3)} seconds</span>
          </div>
          <ul className="mt-4">
            {intervals.map(([start, end], index) => (
              <li key={index} className="flex justify-between items-center mb-2">
                <span>{`Interval ${index + 1}: ${start.toFixed(3)}s - ${end.toFixed(3)}s`}</span>
                <button 
                  onClick={() => removeInterval(index)}
                  className="bg-red-500 text-white p-1 text-sm"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
