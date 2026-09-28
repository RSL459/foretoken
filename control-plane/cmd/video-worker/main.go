// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

// Executes one controller-owned asynchronous video task.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"os"
	"path/filepath"
	"strconv"
)

type inputFile struct {
	Field       string `json:"field"`
	Path        string `json:"path"`
	ContentType string `json:"contentType"`
}

type videoRequest struct {
	Task              string      `json:"task"`
	Prompt            string      `json:"prompt"`
	Width             int32       `json:"width"`
	Height            int32       `json:"height"`
	NumFrames         int32       `json:"numFrames"`
	FPS               int32       `json:"fps"`
	NumInferenceSteps int32       `json:"numInferenceSteps"`
	AspectRatio       string      `json:"aspectRatio,omitempty"`
	FlowShift         *float64    `json:"flowShift,omitempty"`
	AudioFlowShift    *float64    `json:"audioFlowShift,omitempty"`
	Seed              *int64      `json:"seed,omitempty"`
	FrameIndices      []int32     `json:"frameIndices,omitempty"`
	InputFiles        []inputFile `json:"inputFiles,omitempty"`
}

func main() {
	request, err := decodeRequest(os.Getenv("FORETOKEN_VIDEO_REQUEST_JSON"))
	if err != nil {
		fatal(err)
	}
	endpoint := os.Getenv("FORETOKEN_VIDEO_ENDPOINT")
	model := os.Getenv("FORETOKEN_VIDEO_MODEL")
	outputPath := os.Getenv("FORETOKEN_VIDEO_OUTPUT_PATH")
	outputMount := os.Getenv("FORETOKEN_VIDEO_OUTPUT_MOUNT")
	if endpoint == "" || model == "" || outputPath == "" || outputMount == "" {
		fatal(fmt.Errorf("FORETOKEN_VIDEO_ENDPOINT, FORETOKEN_VIDEO_MODEL, FORETOKEN_VIDEO_OUTPUT_PATH and FORETOKEN_VIDEO_OUTPUT_MOUNT are required"))
	}
	if filepath.IsAbs(outputPath) || filepath.Clean(outputPath) == "." || filepath.Clean(outputPath) == ".." {
		fatal(fmt.Errorf("FORETOKEN_VIDEO_OUTPUT_PATH must be a relative path"))
	}
	outputPath = filepath.Join(outputMount, outputPath)

	reader, writer := io.Pipe()
	multipartWriter := multipart.NewWriter(writer)
	errCh := make(chan error, 1)
	for index := range request.InputFiles {
		if !filepath.IsAbs(request.InputFiles[index].Path) {
			request.InputFiles[index].Path = filepath.Join(outputMount, request.InputFiles[index].Path)
		}
	}
	go func() {
		errCh <- writeMultipart(multipartWriter, request, model)
	}()

	httpRequest, err := http.NewRequest(http.MethodPost, endpoint+"/v1/videos/sync", reader)
	if err != nil {
		fatal(err)
	}
	httpRequest.Header.Set("Content-Type", multipartWriter.FormDataContentType())
	response, err := (&http.Client{}).Do(httpRequest)
	if err != nil {
		fatal(err)
	}
	defer response.Body.Close()
	if err := <-errCh; err != nil {
		fatal(err)
	}
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
		fatal(fmt.Errorf("video backend returned %s: %s", response.Status, string(body)))
	}
	if err := os.MkdirAll(filepath.Dir(outputPath), 0o750); err != nil {
		fatal(err)
	}
	output, err := os.OpenFile(outputPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o640)
	if err != nil {
		fatal(err)
	}
	_, copyErr := io.Copy(output, response.Body)
	closeErr := output.Close()
	if copyErr != nil {
		fatal(copyErr)
	}
	if closeErr != nil {
		fatal(closeErr)
	}
}

func decodeRequest(value string) (videoRequest, error) {
	if value == "" {
		return videoRequest{}, fmt.Errorf("FORETOKEN_VIDEO_REQUEST_JSON is required")
	}
	var request videoRequest
	if err := json.Unmarshal([]byte(value), &request); err != nil {
		return videoRequest{}, fmt.Errorf("decode video request: %w", err)
	}
	return request, nil
}

func writeMultipart(writer *multipart.Writer, request videoRequest, model string) error {
	defer writer.Close()
	extraParams := map[string]any{"task": request.Task}
	if request.AudioFlowShift != nil {
		extraParams["audio_flow_shift"] = *request.AudioFlowShift
	}
	if len(request.FrameIndices) > 0 {
		extraParams["frame_indices"] = request.FrameIndices
	}
	extraJSON, err := json.Marshal(extraParams)
	if err != nil {
		return err
	}
	fields := map[string]string{
		"model":               model,
		"prompt":              request.Prompt,
		"width":               strconv.FormatInt(int64(request.Width), 10),
		"height":              strconv.FormatInt(int64(request.Height), 10),
		"num_frames":          strconv.FormatInt(int64(request.NumFrames), 10),
		"fps":                 strconv.FormatInt(int64(request.FPS), 10),
		"num_inference_steps": strconv.FormatInt(int64(request.NumInferenceSteps), 10),
		"extra_params":        string(extraJSON),
	}
	if request.AspectRatio != "" {
		fields["aspect_ratio"] = request.AspectRatio
	}
	if request.FlowShift != nil {
		fields["flow_shift"] = strconv.FormatFloat(*request.FlowShift, 'f', -1, 64)
	}
	if request.Seed != nil {
		fields["seed"] = strconv.FormatInt(*request.Seed, 10)
	}
	for name, value := range fields {
		if err := writer.WriteField(name, value); err != nil {
			return err
		}
	}
	for _, input := range request.InputFiles {
		file, err := os.Open(input.Path)
		if err != nil {
			return fmt.Errorf("open %s: %w", input.Path, err)
		}
		header := make(textproto.MIMEHeader)
		header.Set("Content-Disposition", fmt.Sprintf(`form-data; name=%q; filename=%q`, input.Field, filepath.Base(input.Path)))
		if input.ContentType != "" {
			header.Set("Content-Type", input.ContentType)
		}
		part, err := writer.CreatePart(header)
		if err == nil {
			_, err = io.Copy(part, file)
		}
		closeErr := file.Close()
		if err != nil {
			return err
		}
		if closeErr != nil {
			return closeErr
		}
	}
	return nil
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
