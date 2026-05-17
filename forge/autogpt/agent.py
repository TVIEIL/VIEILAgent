import requests
import json
import subprocess
import pathlib
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from hypercorn.asyncio import serve
from hypercorn.config import Config

from autogpt.sdk import Agent, AgentDB, Step, StepRequestBody, Workspace
from autogpt.sdk.middlewares import AgentMiddleware

class AutoGPTAgent(Agent):
    """
    VIEILagent - Agent expert en système et électronique.
    Développé pour l'écosystème distribué Natacha.
    """

    def __init__(self, database: AgentDB, workspace: Workspace):
        super().__init__(database, workspace)

    def start(self, port: int = 8000, router = None):
        """
        SURCHARGE RADICALE : On force FastAPI à utiliser CETTE instance personnalisée.
        """
        config = Config()
        config.bind = [f"0.0.0.0:{port}"]
        
        app = FastAPI(
            title="Auto-GPT Forge - VIEILagent",
            description="Version modifiée et connectée à Ollama",
            version="v1.0",
        )

        origins = ["*"]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        if router:
            app.include_router(router)
            
        # ICI : On injecte explicitement 'self' (ton agent personnalisé) dans le middleware !
        app.add_middleware(AgentMiddleware, agent=self)
        config.loglevel = "ERROR"

        print(f"🚀 [VIEILagent] Le serveur démarre sur http://0.0.0.0:{port} avec la logique Ollama active !")
        asyncio.run(serve(app, config))

    async def execute_step(self, task_id: str, step_request: StepRequestBody) -> Step:
        # 1. Créer l'étape dans la base de données de la Forge
        step = await self.db.create_step(task_id=task_id, input=step_request, is_last=True)
        
        # 2. Récupérer la tâche globale pour avoir la vraie mission d'origine
        task = await self.db.get_task(task_id=task_id)
        cahier_des_charges = task.input
        print(f"\n🧠 [VIEILagent] Mission d'origine récupérée en BDD : {cahier_des_charges}")

        # 3. Configurer l'appel à ton Ollama local
        OLLAMA_URL = "http://localhost:11434/api/generate"
        MODEL_NAME = "qwen2.5-coder:14b"

        prompt = f"""Tu es VIEILagent, un ingénieur système et électronicien expert en C++.
Génère UNIQUEMENT le code C++ complet, propre et fonctionnel qui répond au cahier des charges suivant.
Ne mets AUCUNE explication, aucun blabla, juste le code dans un bloc de code.

Cahier des charges :
{cahier_des_charges}
"""

        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }

        # 4. Demander au cerveau local de concevoir l'application
        try:
            print(f"🤖 Interrogation de Ollama ({MODEL_NAME})...")
            response = requests.post(OLLAMA_URL, json=payload, timeout=180)
            result = response.json()
            code_genere = result.get("response", "").strip()
            
            if "```" in code_genere:
                code_genere = code_genere.split("```")[1]
                if code_genere.startswith("cpp"):
                    code_genere = code_genere[3:]
            code_genere = code_genere.strip()

        except Exception as e:
            error_msg = f"❌ Erreur de connexion à Ollama : {e}"
            print(error_msg)
            step.output = error_msg
            return step

        # 5. Écrire le code C++ dans le Workspace de l'agent
        nom_fichier = "main.cpp"
        self.workspace.write(task_id=task_id, path=nom_fichier, data=code_genere.encode('utf-8'))
        print(f"💾 Fichier {nom_fichier} écrit avec succès dans le workspace.")

        # 6. SANDBOX : Phase de test de compilation automatique avec g++
        # CORRECTION : On rajoute task_id dans le chemin !
        chemin_complet_cpp = pathlib.Path(self.workspace.base_path) / task_id / nom_fichier
        chemin_binaire = pathlib.Path(self.workspace.base_path) / task_id / "compteur_linux"

        print(f"⚙️ Lancement de la compilation de test (g++) sur : {chemin_complet_cpp}")
        
        compilation = subprocess.run(
            ["g++", "-O3", str(chemin_complet_cpp), "-o", str(chemin_binaire), "-lsfml-graphics", "-lsfml-window", "-lsfml-system"],
            capture_output=True, text=True
        )

        if compilation.returncode == 0:
            status_output = f"✅ Application compilée avec succès ! Le binaire est prêt.\n\nCode généré :\n{code_genere}"
            print("🚀 Compilation réussie !")
        else:
            status_output = f"❌ Erreur de compilation détectée par la Sandbox :\n{compilation.stderr}"
            print(f"\n--- CODE GÉNÉRÉ QUI A ÉCHOUÉ ---\n{code_genere}\n--------------------------------")
            print(f"⚠️ Erreur g++ :\n{compilation.stderr}")

        # Enregistrer l'artéfact généré dans la Forge pour le suivi
        await self.db.create_artifact(
            task_id=task_id,
            step_id=step.step_id,
            file_name=nom_fichier,
            relative_path="",
            agent_created=True,
        )

        step.output = status_output
        return step
