import React, { useState, useRef, useEffect } from 'react';
import {
  Camera,
  X,
  RefreshCw,
  Sparkles,
  AlertCircle,
  Upload,
  CheckCircle2,
  Info,
  Maximize2
} from 'lucide-react';
import { scanMeasurement } from '../api';

export default function CameraScannerModal({
  isOpen,
  onClose,
  onScanComplete,
  preferredParameter = null
}) {
  const [stream, setStream] = useState(null);
  const [cameraError, setCameraError] = useState(null);
  const [capturing, setCapturing] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [capturedImage, setCapturedImage] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [facingMode, setFacingMode] = useState('environment'); // 'environment' (trasera) o 'user' (frontal)

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);

  const triggerHaptic = (pattern = 30) => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(pattern);
    }
  };

  // Iniciar la cámara al abrir el modal
  useEffect(() => {
    if (isOpen) {
      setCameraError(null);
      setCapturedImage(null);
      setAnalysisResult(null);
      startCamera(facingMode);
    } else {
      stopCamera();
    }
    return () => {
      stopCamera();
    };
  }, [isOpen, facingMode]);

  const startCamera = async (mode) => {
    stopCamera();
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('La API de cámara (getUserMedia) no está soportada en este navegador o entorno.');
      }

      const constraints = {
        video: {
          facingMode: { ideal: mode },
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false
      };

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (err) {
      console.warn('Error al acceder a la cámara:', err);
      let msg = 'No se pudo acceder a la cámara trasera.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        msg = 'Permiso denegado. Permite el acceso a la cámara en los ajustes de tu navegador.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        msg = 'No se detectó ninguna cámara disponible en tu dispositivo.';
      }
      setCameraError(msg);
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  // Alternar entre cámara trasera y frontal
  const toggleFacingMode = () => {
    triggerHaptic(20);
    setFacingMode(prev => (prev === 'environment' ? 'user' : 'environment'));
  };

  // Capturar imagen desde el video stream y comprimir a WebP
  const capturePhoto = () => {
    if (!videoRef.current) return;
    triggerHaptic(50);
    setCapturing(true);

    try {
      const video = videoRef.current;
      const canvas = canvasRef.current || document.createElement('canvas');

      // Escalar la imagen manteniendo resolución nítida para OCR (máx 1280px)
      const maxDim = 1280;
      let width = video.videoWidth || 1280;
      let height = video.videoHeight || 720;

      if (width > maxDim || height > maxDim) {
        if (width > height) {
          height = Math.round((height * maxDim) / width);
          width = maxDim;
        } else {
          width = Math.round((width * maxDim) / height);
          height = maxDim;
        }
      }

      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, width, height);

      // Comprimir a formato WebP (calidad 85%) con fallback automático del navegador
      const webpDataUrl = canvas.toDataURL('image/webp', 0.85);
      setCapturedImage(webpDataUrl);
      stopCamera();

      // Enviar de inmediato a análisis con el modelo de visión
      processImageWithVision(webpDataUrl);
    } catch (err) {
      console.error('Error al capturar la foto:', err);
      setCameraError('No se pudo procesar el fotograma de la cámara.');
    } finally {
      setCapturing(false);
    }
  };

  // Manejo de archivo manual como fallback (en caso de permisos denegados o desktop)
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    triggerHaptic(30);
    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = canvasRef.current || document.createElement('canvas');
        const maxDim = 1280;
        let width = img.width;
        let height = img.height;

        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        const webpDataUrl = canvas.toDataURL('image/webp', 0.85);
        setCapturedImage(webpDataUrl);
        stopCamera();
        processImageWithVision(webpDataUrl);
      };
      img.src = event.target.result;
    };
    reader.readAsDataURL(file);
  };

  // Envío al backend FastAPI con Gemini Vision
  const processImageWithVision = async (imageData) => {
    setAnalyzing(true);
    setCameraError(null);
    try {
      const result = await scanMeasurement(imageData, preferredParameter);
      setAnalysisResult(result);
      triggerHaptic([40, 60, 100]);

      // Si se detectó un valor exitosamente, autocompletar tras breve confirmación
      if (result.success && result.value !== null && result.parameter) {
        setTimeout(() => {
          onScanComplete(result);
          onClose();
        }, 1400);
      }
    } catch (err) {
      console.error('Error analizando test:', err);
      setCameraError(err.message || 'Error al comunicarse con el modelo de visión IA.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRetake = () => {
    triggerHaptic(20);
    setCapturedImage(null);
    setAnalysisResult(null);
    setCameraError(null);
    startCamera(facingMode);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/85 backdrop-blur-md animate-in fade-in">
      <div className="relative w-full max-w-lg bg-marine-950 border border-cyan-500/30 rounded-3xl overflow-hidden shadow-2xl flex flex-col max-h-[92vh]">
        {/* Header Modal */}
        <div className="p-4 bg-marine-900/90 border-b border-marine-800 flex items-center justify-between z-20">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <Camera className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                Escaneo Visual con IA
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  Hanna / Salifert
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">Encuadra la pantalla o vial de tu test</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-marine-800/80 hover:bg-marine-700 text-slate-300 hover:text-white flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Viewfinder / Visor de la Cámara con Superposición */}
        <div className="relative flex-1 bg-black min-h-[360px] sm:min-h-[420px] flex items-center justify-center overflow-hidden">
          {/* Video en vivo */}
          {!capturedImage ? (
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 w-full h-full object-cover"
            />
          ) : (
            <img
              src={capturedImage}
              alt="Test Capturado"
              className="absolute inset-0 w-full h-full object-contain bg-marine-950"
            />
          )}

          {/* Superposición Visual: Recuadro Guía y Máscara Oscurecida */}
          {!capturedImage && !cameraError && (
            <div className="absolute inset-0 pointer-events-none flex flex-col items-center justify-center p-6">
              {/* Marco de encuadre translúcido */}
              <div className="relative w-64 h-64 sm:w-72 sm:h-72 rounded-3xl border-2 border-cyan-400/80 shadow-[0_0_25px_rgba(0,242,254,0.35)] flex items-center justify-center">
                {/* Esquinas resaltadas */}
                <div className="absolute -top-1 -left-1 w-6 h-6 border-t-4 border-l-4 border-cyan-400 rounded-tl-lg" />
                <div className="absolute -top-1 -right-1 w-6 h-6 border-t-4 border-r-4 border-cyan-400 rounded-tr-lg" />
                <div className="absolute -bottom-1 -left-1 w-6 h-6 border-b-4 border-l-4 border-cyan-400 rounded-bl-lg" />
                <div className="absolute -bottom-1 -right-1 w-6 h-6 border-b-4 border-r-4 border-cyan-400 rounded-br-lg" />

                {/* Línea de escaneo láser animada */}
                <div className="absolute inset-x-2 h-0.5 bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_12px_#00f2fe] animate-pulse" />

                {/* Icono central de encuadre */}
                <Maximize2 className="w-8 h-8 text-cyan-400/30" />
              </div>

              {/* Instrucción visual flotante */}
              <div className="mt-4 px-3.5 py-1.5 rounded-full bg-marine-950/80 backdrop-blur-md border border-cyan-500/30 text-[11px] font-semibold text-cyan-200 text-center shadow-lg">
                Centra la pantalla digital de tu Hanna Checker o escala Salifert
              </div>
            </div>
          )}

          {/* Estado de Análisis con IA */}
          {analyzing && (
            <div className="absolute inset-0 bg-marine-950/80 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center z-30 animate-in fade-in">
              <div className="w-16 h-16 rounded-full bg-cyan-500/20 border-2 border-cyan-400 flex items-center justify-center mb-4 relative">
                <Sparkles className="w-8 h-8 text-cyan-300 animate-spin" />
                <div className="absolute inset-0 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
              </div>
              <h4 className="text-base font-extrabold text-white mb-1">
                Analizando con Modelo de Visión...
              </h4>
              <p className="text-xs text-slate-300 max-w-xs">
                Extrayendo parámetros químicos y valor numérico de tu test.
              </p>
            </div>
          )}

          {/* Resultado Exitoso */}
          {analysisResult && analysisResult.success && analysisResult.value !== null && (
            <div className="absolute inset-0 bg-marine-950/90 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center z-30 animate-in zoom-in-95">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center mb-3">
                <CheckCircle2 className="w-9 h-9 text-emerald-400" />
              </div>
              <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-1">
                {analysisResult.kit_detected || 'Lectura Detectada'}
              </span>
              <div className="text-3xl font-black text-white mb-1 font-mono">
                {analysisResult.value}
                <span className="text-base text-cyan-400 ml-1.5 font-sans font-bold">
                  {analysisResult.parameter?.replace('_', ' ').toUpperCase()}
                </span>
              </div>
              <p className="text-xs text-slate-300 max-w-sm mb-3">
                {analysisResult.notes || 'Autocompletando formulario...'}
              </p>
              {!analysisResult.api_key_configured && (
                <div className="text-[10px] bg-amber-500/15 border border-amber-500/30 text-amber-300 px-3 py-1 rounded-xl">
                  {analysisResult.message}
                </div>
              )}
            </div>
          )}

          {/* Error de Cámara o Permisos */}
          {cameraError && !analyzing && (
            <div className="absolute inset-0 bg-marine-950/95 flex flex-col items-center justify-center p-6 text-center z-30">
              <AlertCircle className="w-12 h-12 text-coral-400 mb-3" />
              <h4 className="text-sm font-bold text-white mb-1">Cámara no disponible</h4>
              <p className="text-xs text-slate-400 max-w-xs mb-4">{cameraError}</p>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="btn-touch py-2.5 px-4 bg-cyan-500 text-marine-950 text-xs font-black flex items-center gap-2 rounded-xl"
              >
                <Upload className="w-4 h-4" />
                <span>Subir Foto desde Galería</span>
              </button>
            </div>
          )}
        </div>

        {/* Input file oculto para fallback */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFileUpload}
          className="hidden"
        />

        {/* Offscreen Canvas para compresión a WebP */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Barra de Controles Inferior */}
        <div className="p-4 bg-marine-900 border-t border-marine-800 flex items-center justify-between gap-3 z-20">
          {!capturedImage ? (
            <>
              {/* Botón de Galería */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-11 h-11 rounded-2xl bg-marine-800 hover:bg-marine-700 text-slate-300 flex items-center justify-center transition-colors"
                title="Subir imagen"
              >
                <Upload className="w-5 h-5" />
              </button>

              {/* Botón Central de Disparo Grande (Shutter táctil para dedos mojados) */}
              <button
                type="button"
                onClick={capturePhoto}
                disabled={capturing || !!cameraError}
                className="w-16 h-16 rounded-full bg-gradient-to-tr from-cyan-500 to-emerald-400 p-1 shadow-neon-cyan active:scale-95 transition-transform flex items-center justify-center disabled:opacity-40"
              >
                <div className="w-full h-full rounded-full border-2 border-marine-950 bg-white/20 flex items-center justify-center">
                  <div className="w-8 h-8 rounded-full bg-white shadow-inner" />
                </div>
              </button>

              {/* Botón para alternar cámara (trasera / frontal) */}
              <button
                type="button"
                onClick={toggleFacingMode}
                className="w-11 h-11 rounded-2xl bg-marine-800 hover:bg-marine-700 text-slate-300 flex items-center justify-center transition-colors"
                title="Cambiar cámara"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </>
          ) : (
            <div className="w-full flex items-center gap-3">
              <button
                type="button"
                onClick={handleRetake}
                disabled={analyzing}
                className="btn-touch-secondary flex-1 py-3 text-xs font-bold flex items-center justify-center gap-2 rounded-xl"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Repetir Foto</span>
              </button>
              {analysisResult && !analysisResult.success && (
                <button
                  type="button"
                  onClick={() => processImageWithVision(capturedImage)}
                  disabled={analyzing}
                  className="btn-touch flex-1 py-3 bg-cyan-500 text-marine-950 text-xs font-extrabold flex items-center justify-center gap-2 rounded-xl"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Reintentar Análisis</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
