from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, Response, jsonify
import json
from .backend_services import (
    register_user, login_user,
    list_user_documents, get_doc_by_filename,
    upload_pdf_blob, create_document_row, update_document_status,
    extract_text_from_pdf_bytes, create_index_and_ingest, build_qa_chain,
    add_question_history, list_questions_history, documents_table, UpdateMode,
    delete_questions_for_user, delete_question, delete_question_by_keys,
    get_blob_size_from_url, clean_response, stream_qa_response, cleanup_orphaned_documents
)
import uuid
from datetime import datetime


bp = Blueprint("main", __name__)


def require_login():
    if not session.get("user_id"):
        return redirect(url_for("main.login"))
    return None


@bp.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        ok, user_id = login_user(email, password)
        if ok:
            session["user_id"] = user_id
            session["email"] = email
            return redirect(url_for("main.dashboard"))
        flash("Email ou mot de passe incorrect", "error")
    return render_template("auth/login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        ok, msg = register_user(email, password)
        flash(msg, "info" if ok else "error")
        if ok:
            return redirect(url_for("main.login"))
    return render_template("auth/register.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/dashboard")
def dashboard():
    if (r := require_login()) is not None:
        return r
    user_id = session["user_id"]
    docs = list_user_documents(user_id)
    questions = list_questions_history(user_id)
    total_docs = len(docs)
    total_questions = len(questions)
    used_space_kb = 0.0
    for d in docs:
        try:
            size = d.get("FileSize")
            if not size and d.get("BlobURL"):
                size = get_blob_size_from_url(d.get("BlobURL"))
                if size:
                    ent = documents_table.get_entity(partition_key=user_id, row_key=d["RowKey"])
                    ent["FileSize"] = int(size)
                    documents_table.update_entity(ent, mode=UpdateMode.MERGE)
            used_space_kb += float(size or 0) / 1024.0
        except Exception:
            pass
    return render_template("dashboard.html", total_docs=total_docs, total_questions=total_questions, used_space_kb=used_space_kb, recent_docs=docs[:5], recent_questions=questions[:5])


@bp.route("/documents", methods=["GET", "POST"])
def documents():
    if (r := require_login()) is not None:
        return r
    user_id = session["user_id"]
    
    # Nettoyer les documents orphelins à chaque chargement de la page
    try:
        cleaned_count = cleanup_orphaned_documents(user_id)
        if cleaned_count > 0:
            flash(f"Nettoyage automatique: {cleaned_count} document(s) orphelin(s) supprimé(s).", "info")
    except Exception as e:
        print(f"Erreur lors du nettoyage automatique: {e}")
    
    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename.lower().endswith(".pdf"):
            filename = file.filename
            existing = get_doc_by_filename(user_id, filename)
            file_bytes = file.read()
            file_size_bytes = len(file_bytes) if file_bytes is not None else 0
            if existing and existing.get("Status") == "indexed":
                flash("Le document est déjà indexé.", "warning")
            else:
                if existing:
                    blob_url = existing.get("BlobURL")
                    if not blob_url:
                        blob_url = upload_pdf_blob(user_id, filename, file_bytes)
                        ent = documents_table.get_entity(partition_key=user_id, row_key=existing["RowKey"])
                        ent["BlobURL"] = blob_url
                        ent["UploadDate"] = datetime.utcnow().isoformat() + "Z"
                        ent["FileSize"] = int(file_size_bytes)
                        documents_table.update_entity(ent, mode=UpdateMode.MERGE)
                    index_name = existing["IndexName"]
                    doc_id = existing["RowKey"]
                    # Ensure FileSize is present for existing docs
                    try:
                        ent = documents_table.get_entity(partition_key=user_id, row_key=doc_id)
                        if not ent.get("FileSize"):
                            size = int(file_size_bytes) if file_size_bytes else (
                                get_blob_size_from_url(ent.get("BlobURL", ""))
                            )
                            if size:
                                ent["FileSize"] = int(size)
                            documents_table.update_entity(ent, mode=UpdateMode.MERGE)
                    except Exception:
                        pass
                    update_document_status(user_id, doc_id, "indexing")
                else:
                    blob_url = upload_pdf_blob(user_id, filename, file_bytes)
                    doc_suffix = uuid.uuid4().hex[:8]
                    index_name = f"index_user{user_id}_doc{doc_suffix}".lower()
                    doc_id = create_document_row(user_id, filename, blob_url, index_name, status="indexing", file_size_bytes=file_size_bytes)

                text = extract_text_from_pdf_bytes(file_bytes)
                create_index_and_ingest(text, index_name)
                update_document_status(user_id, doc_id, "indexed")
                flash("Document indexé avec succès.", "success")
        else:
            flash("Veuillez sélectionner un PDF.", "error")
    docs = list_user_documents(user_id)
    return render_template("documents.html", docs=docs)


@bp.route("/delete_document", methods=["POST"])
def delete_document():
    if (r := require_login()) is not None:
        return r
    user_id = session["user_id"]
    doc_id = request.form.get("doc_id")
    
    if not doc_id:
        flash("ID du document manquant.", "error")
        return redirect(url_for("main.documents"))
    
    try:
        # Vérifier si le document existe avant de le supprimer
        try:
            doc = documents_table.get_entity(partition_key=user_id, row_key=doc_id)
        except Exception as e:
            if "ResourceNotFound" in str(e) or "does not exist" in str(e):
                flash("Le document a déjà été supprimé ou n'existe pas.", "warning")
                return redirect(url_for("main.documents"))
            else:
                raise e
        
        # Supprimer l'index de recherche si il existe
        index_name = doc.get("IndexName")
        if index_name:
            try:
                # Supprimer l'index Azure Search (à implémenter si nécessaire)
                # Pour l'instant, on passe car la suppression d'index n'est pas critique
                pass
            except Exception as e:
                print(f"Erreur lors de la suppression de l'index {index_name}: {e}")
        
        # Supprimer l'entrée de la base de données
        try:
            documents_table.delete_entity(partition_key=user_id, row_key=doc_id)
            flash("Document supprimé avec succès.", "success")
        except Exception as e:
            if "ResourceNotFound" in str(e) or "does not exist" in str(e):
                flash("Le document a déjà été supprimé de la base de données.", "warning")
            else:
                raise e
                
    except Exception as e:
        flash(f"Erreur lors de la suppression: {str(e)}", "error")
    
    return redirect(url_for("main.documents"))


@bp.route("/cleanup_documents", methods=["POST"])
def cleanup_documents():
    """Route pour forcer le nettoyage des documents orphelins."""
    if (r := require_login()) is not None:
        return r
    
    user_id = session["user_id"]
    try:
        cleaned_count = cleanup_orphaned_documents(user_id)
        if cleaned_count > 0:
            flash(f"Nettoyage réussi: {cleaned_count} document(s) orphelin(s) supprimé(s).", "success")
        else:
            flash("Aucun document orphelin trouvé.", "info")
    except Exception as e:
        flash(f"Erreur lors du nettoyage: {str(e)}", "error")
    
    return redirect(url_for("main.documents"))


@bp.route("/rag", methods=["GET", "POST"])
def rag():
    if (r := require_login()) is not None:
        return r
    user_id = session["user_id"]
    docs = [d for d in list_user_documents(user_id) if d.get("Status") == "indexed"]
    answer = None
    chosen_doc = None
    if request.method == "POST":
        doc_filename = request.form.get("document")
        question = request.form.get("question", "").strip()
        if doc_filename and question:
            try:
                chosen_doc = get_doc_by_filename(user_id, doc_filename)
                qa_chain = build_qa_chain(chosen_doc["IndexName"])
                result = qa_chain.invoke({"input": question})
                raw_answer = result.get("answer", "")
                # Nettoyer la réponse pour supprimer les sections de réflexion
                answer = clean_response(raw_answer)
                add_question_history(user_id, doc_filename, question, str(answer))
            except Exception as e:
                flash(f"Erreur lors du traitement de la question: {str(e)}", "error")
                answer = f"Erreur: {str(e)}"
    history = list_questions_history(user_id)
    return render_template("rag.html", docs=docs, answer=answer, chosen_doc=chosen_doc, history=history)


@bp.route("/clear_history", methods=["POST"])
def clear_history():
    if (r := require_login()) is not None:
        return r
    user_id = session["user_id"]
    try:
        deleted = delete_questions_for_user(user_id)
        flash(f"Historique supprimé ({deleted} éléments)", "success")
    except Exception as e:
        flash(f"Erreur lors de la suppression de l'historique: {str(e)}", "error")
    return redirect(url_for("main.rag"))


@bp.route("/delete_question", methods=["POST"])
def delete_question_route():
    if (r := require_login()) is not None:
        return r
    user_id = session["user_id"]
    qid = request.form.get("question_id")
    pk = request.form.get("partition_key")
    if not qid:
        flash("ID de la question manquant.", "error")
        return redirect(url_for("main.rag"))
    # If UI provided a PartitionKey, use it to avoid mismatch
    if pk:
        # Allow only current user's partition
        if pk != user_id:
            flash("Suppression non autorisée pour cette partition.", "error")
            return redirect(url_for("main.rag"))
        ok = delete_question_by_keys(pk, qid)
    else:
        ok = delete_question(user_id, qid)
    if ok:
        flash("Question supprimée.", "success")
    else:
        flash("Échec de la suppression de la question.", "error")
    return redirect(url_for("main.rag"))


@bp.route("/rag_stream", methods=["POST"])
def rag_stream():
    """Route pour le streaming de la réponse RAG via Server-Sent Events."""
    if (r := require_login()) is not None:
        return r
    
    user_id = session["user_id"]
    doc_filename = request.json.get("document")
    question = request.json.get("question", "").strip()
    
    if not doc_filename or not question:
        return jsonify({"error": "Document et question requis"}), 400
    
    try:
        chosen_doc = get_doc_by_filename(user_id, doc_filename)
        if not chosen_doc:
            return jsonify({"error": "Document non trouvé"}), 404
        
        def generate():
            """Générateur pour Server-Sent Events."""
            try:
                # Envoyer un événement de début
                yield f"data: {json.dumps({'type': 'start', 'message': 'Génération de la réponse...'})}\n\n"
                
                full_answer = ""
                
                # Streamer la réponse chunk par chunk
                for chunk in stream_qa_response(chosen_doc["IndexName"], question):
                    if chunk:
                        full_answer += chunk
                        # Envoyer chaque chunk comme un événement SSE
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                # Envoyer un événement de fin
                yield f"data: {json.dumps({'type': 'end', 'message': 'Réponse complète'})}\n\n"
                
                # Sauvegarder dans l'historique
                add_question_history(user_id, doc_filename, question, full_answer)
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )
        
    except Exception as e:
        return jsonify({"error": f"Erreur lors du traitement: {str(e)}"}), 500


