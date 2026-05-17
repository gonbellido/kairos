"""Telegram bot multi-coach con multi-idioma ES/EN."""

import logging
from uuid import uuid4

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

from kairos.core.client import ClientProfile
from kairos.engine.activity import log_activity

logger = logging.getLogger(__name__)

REG_NAME, REG_CONTEXT, CHATTING = range(3)

# ── i18n messages ──
T = {
    "es": {
        "welcome_back": "👋 Bienvenido de nuevo, {name}!\n\nEscribe tu mensaje para continuar con tu sesión de coaching.\n🎤 También puedes enviar audios.",
        "welcome_new": "👋 *Bienvenido a KAIROS Coaching!*\n\nPara comenzar, necesito registrarte. ¿Cuál es tu nombre?",
        "ask_name": "Encantado, {name}! Cuéntame brevemente ¿qué te gustaría trabajar en estas sesiones? (opcional, escribe 'ninguno' para saltar)",
        "reg_done": "✅ *Registro completado!*\n\nBienvenido, {name}. Ya puedes empezar a escribir tus mensajes.\n\n💬 Escribe lo que quieras trabajar hoy.\n🎤 También puedes enviar audios.\n📁 O enviar documentos (PDF, texto).",
        "not_registered": "No estás registrado. Usa /start para comenzar.",
        "doc_received": "✅ Documento recibido: {name}",
        "transcript": "📝 *Transcripción:*\n{text}",
        "transcript_fail": "❌ No pude transcribir el audio.",
        "transcript_unavailable": "⏳ Transcripción no disponible ahora. Tu audio fue recibido.",
        "help_text": "🤖 *KAIROS Coaching*\n\n/start — Iniciar o reanudar sesión\n/help — Esta ayuda\n\n💬 Escribe tu mensaje para conversar\n🎤 Envía audios para transcribirlos\n📁 Envía documentos para guardarlos",
    },
    "en": {
        "welcome_back": "👋 Welcome back, {name}!\n\nWrite your message to continue your coaching session.\n🎤 You can also send audios.",
        "welcome_new": "👋 *Welcome to KAIROS Coaching!*\n\nTo get started, I need to register you. What's your name?",
        "ask_name": "Nice to meet you, {name}! Tell me briefly, what would you like to work on in these sessions? (optional, type 'none' to skip)",
        "reg_done": "✅ *Registration complete!*\n\nWelcome, {name}. You can now start writing your messages.\n\n💬 Write what you'd like to work on today.\n🎤 You can also send audios.\n📁 Or send documents (PDF, text).",
        "not_registered": "You are not registered. Use /start to begin.",
        "doc_received": "✅ Document received: {name}",
        "transcript": "📝 *Transcript:*\n{text}",
        "transcript_fail": "❌ Could not transcribe the audio.",
        "transcript_unavailable": "⏳ Transcription not available right now. Your audio was received.",
        "help_text": "🤖 *KAIROS Coaching*\n\n/start — Start or resume session\n/help — This help\n\n💬 Write your message to chat\n🎤 Send audios to transcribe\n📁 Send documents to save",
    },
}


class KairosTelegramBot:
    def __init__(self, token: str, runtime=None, coach_id: str = "default", lang: str = "es", journey_engine=None):
        self._token = token
        self._runtime = runtime
        self._coach_id = coach_id
        self._lang = lang if lang in ("es", "en") else "es"
        self._app: Application | None = None
        self._je = journey_engine

    @property
    def coach_id(self) -> str:
        return self._coach_id

    def t(self, key: str, **kwargs) -> str:
        msg = T.get(self._lang, T["es"]).get(key, key)
        if kwargs:
            msg = msg.format(**kwargs)
        return msg

    async def _get_client_by_telegram(self, telegram_id: str) -> ClientProfile | None:
        store = self._runtime.client_store
        from qdrant_client.http import models as qdrant_models
        results = store._client.query_points(
            collection_name="client_profiles",
            query=[0.0] * store._embeddings.dimensions,
            query_filter=qdrant_models.Filter(
                must=[qdrant_models.FieldCondition(
                    key="metadata.telegram_id",
                    match=qdrant_models.MatchValue(value=telegram_id),
                )],
            ),
            limit=1, with_payload=True,
        )
        return ClientProfile(**results.points[0].payload) if results.points else None

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_id = str(update.effective_user.id)
        log_activity("tg_start", {"telegram_id": telegram_id, "channel": "telegram"})
        existing = await self._get_client_by_telegram(telegram_id)
        if existing:
            await update.message.reply_text(
                self.t("welcome_back", name=existing.nombre)
            )
            context.user_data["client_id"] = existing.id
            return CHATTING

        await update.message.reply_text(
            self.t("welcome_new"), parse_mode="Markdown"
        )
        return REG_NAME

    async def _reg_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        name = update.message.text.strip()
        if not name or len(name) < 2:
            name = self.t("reg_name_default") if self._lang == "es" else "Guest"
        context.user_data["reg_name"] = name
        await update.message.reply_text(
            self.t("ask_name", name=context.user_data["reg_name"])
        )
        return REG_CONTEXT

    async def _reg_context(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        name = context.user_data.get("reg_name", "Client")
        ctx_text = update.message.text.strip()
        ctx = ctx_text if ctx_text.lower() not in ("ninguno", "none", "skip", "saltar") else ""

        telegram_id = str(update.effective_user.id)
        store = self._runtime.client_store

        profile = ClientProfile(
            id=uuid4().hex,
            coach_id=self._coach_id,
            nombre=name,
            metadata={"telegram_id": telegram_id, "contexto": ctx, "notas": ""},
        )
        await store.upsert_profile(profile)
        context.user_data["client_id"] = profile.id

        # Auto-assign default journey (coaching) for new clients
        if self._je:
            try:
                default_journeys = await self._je.list_journeys("default", full=False)
                coach_journeys = await self._je.list_journeys(self._coach_id, full=False)
                all_j = default_journeys + coach_journeys
                coaching = next((j for j in all_j if j.get("profile_type") == "coaching"), all_j[0] if all_j else None)
                if coaching:
                    await self._je.assign_client(profile.id, self._coach_id, coaching["id"])
                    log_activity("journey_assigned", {"client_id": profile.id, "journey": coaching["name"], "channel": "telegram"})
            except Exception:
                pass

        await update.message.reply_text(
            self.t("reg_done", name=name), parse_mode="Markdown"
        )
        return CHATTING

    async def _chat_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        client_id = context.user_data.get("client_id")
        if not client_id:
            await update.message.reply_text(self.t("not_registered"))
            return

        await update.effective_chat.send_action("typing")

        log_activity("tg_message", {"client_id": client_id, "message": update.message.text[:100], "channel": "telegram"})

        ctx = {"client_id": client_id, "client_name": client_id}

        # Journey prompt injection (same as stream.py)
        if self._je:
            try:
                cj = await self._je.get_client_journey(client_id)
                # Auto-assign default journey if none assigned
                if not cj:
                    default_journeys = await self._je.list_journeys("default", full=False)
                    # Try coach's default journey first
                    coach_default = None
                    try:
                        from kairos.db.session import create_session_factory
                        from kairos.engine.coach_auth_pg import CoachDBA
                        db = CoachDBA(create_session_factory())
                        coach_info = await db.get_by_id(self._coach_id)
                        if coach_info:
                            coach_default = coach_info.get("default_journey_id", "")
                    except Exception:
                        pass
                    coaching = next((j for j in default_journeys if j["id"] == coach_default), None) if coach_default else None
                    if not coaching:
                        coaching = next((j for j in default_journeys if j.get("profile_type") == "coaching"), default_journeys[0] if default_journeys else None)
                    if coaching:
                        await self._je.assign_client(client_id, self._coach_id, coaching["id"])
                        cj = await self._je.get_client_journey(client_id)
                        log_activity("journey_assigned", {"client_id": client_id, "journey": coaching["name"], "channel": "telegram"})

                if cj and cj.get("journey"):
                    journey_prompt = await self._je.compose_agent_prompt(client_id, update.message.text)
                    if journey_prompt:
                        ctx["_journey_system_prompt"] = journey_prompt
                        log_activity("journey_prompt", {"client_id": client_id, "agent": cj.get("current_agent_id", "")[:8], "prompt_len": len(journey_prompt), "channel": "telegram"})
            except Exception as e:
                log_activity("journey_error", {"client_id": client_id, "error": str(e)[:100], "channel": "telegram"})

        result = await self._runtime.run(
            session_id=uuid4().hex,
            profile_id="coaching",
            message=update.message.text,
            user_id=client_id,
            context=ctx,
        )
        response = result.get("final_response", "⚠️ No pude procesar tu mensaje. Intenta de nuevo.")
        log_activity("agent_response_tg", {"client_id": client_id, "length": len(response), "channel": "telegram"})
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i + 4000])
        else:
            await update.message.reply_text(response)

    async def _audio_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        client_id = context.user_data.get("client_id")
        if not client_id:
            await update.message.reply_text(self.t("not_registered"))
            return

        await update.effective_chat.send_action("typing")

        file = await update.effective_message.effective_attachment.get_file()
        ogg_path = f"/tmp/kairos_tg_{uuid4().hex}.ogg"
        await file.download_to_drive(ogg_path)

        transcriber = self._runtime.transcriber
        if transcriber.available:
            result = await transcriber.transcribe(ogg_path)
            text = result.get("text", "")
            if text.strip():
                await update.message.reply_text(self.t("transcript", text=text), parse_mode="Markdown")
                result = await self._runtime.run(
                    session_id=uuid4().hex,
                    profile_id="coaching",
                    message=text,
                    user_id=client_id,
                    context={"client_id": client_id, "_audio_path": ogg_path},
                )
                resp = result.get("final_response", "")
                if resp:
                    if len(resp) > 4000:
                        for i in range(0, len(resp), 4000):
                            await update.message.reply_text(resp[i:i + 4000])
                    else:
                        await update.message.reply_text(resp)
            else:
                await update.message.reply_text(self.t("transcript_fail"))
        else:
            await update.message.reply_text(self.t("transcript_unavailable"))

    async def _document_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        client_id = context.user_data.get("client_id")
        if not client_id:
            await update.message.reply_text(self.t("not_registered"))
            return

        file = await update.effective_message.effective_attachment.get_file()
        doc_path = f"/tmp/kairos_doc_{uuid4().hex}"
        await file.download_to_drive(doc_path)

        from kairos.core.memory import RawMemory
        raw = RawMemory(
            profile_id="coaching",
            client_id=client_id,
            content=f"[Documento de cliente] {update.message.document.file_name or 'documento'}",
            source_type="telegram_document",
            metadata={"file_name": update.message.document.file_name},
        )
        await self._runtime.raw_store.store(raw)

        await update.message.reply_text(
            self.t("doc_received", name=update.message.document.file_name or "documento")
        )

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.t("help_text"))

    async def send_alert(self, chat_id: str, message: str, level: str = "medium"):
        icon = {"low": "🟡", "medium": "🟠", "high": "🔴", "urgent": "🚨"}.get(level, "🟡")
        if self._app:
            try:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=f"{icon} *Alerta KAIROS*\n{message}",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.warning("Failed to send alert to %s: %s", chat_id, e)

    def build_app(self) -> Application:
        self._app = Application.builder().token(self._token).build()

        conv = ConversationHandler(
            entry_points=[CommandHandler("start", self._start)],
            states={
                REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self._reg_name)],
                REG_CONTEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self._reg_context)],
                CHATTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, self._chat_message)],
            },
            fallbacks=[CommandHandler("start", self._start)],
        )
        self._app.add_handler(conv)
        self._app.add_handler(CommandHandler("help", self._help))
        self._app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self._audio_message))
        self._app.add_handler(MessageHandler(filters.Document.ALL, self._document_message))

        return self._app

    async def run_webhook(self, webhook_url: str):
        app = self.build_app()
        await app.bot.set_webhook(url=webhook_url)
        await app.start()
        logger.info("Telegram bot webhook [coach=%s]: %s", self._coach_id, webhook_url)
        return app

    async def run_polling(self):
        app = self.build_app()
        logger.info("Telegram bot polling [coach=%s]", self._coach_id)
        await app.run_polling()
