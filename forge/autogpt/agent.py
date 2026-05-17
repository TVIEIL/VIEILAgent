from autogpt.sdk import Agent, AgentDB, Step, StepRequestBody, Workspace


class AutoGPTAgent(Agent):
    """
    The goal of the Forge is to take care of the boilerplate code so you can focus on
    agent design.

    There is a great paper surveying the agent landscape: https://arxiv.org/abs/2308.11432
    Which I would highly recommend reading as it will help you understand the possabilities.

    Here is a summary of the key components of an agent:

    Anatomy of an agent:
         - Profile
         - Memory
         - Planning
         - Action

    Profile:

    Agents typically perform a task by assuming specific roles. For example, a teacher,
    a coder, a planner etc. In using the profile in the llm prompt it has been shown to
    improve the quality of the output. https://arxiv.org/abs/2305.14688

    Additionally baed on the profile selected, the agent could be configured to use a
    different llm. The possabilities are endless and the profile can be selected selected
    dynamically based on the task at hand.

    Memory:

    Memory is critical for the agent to acculmulate experiences, self-evolve, and behave
    in a more consistent, reasonable, and effective manner. There are many approaches to
    memory. However, some thoughts: there is long term and short term or working memory.
    You may want different approaches for each. There has also been work exploring the
    idea of memory reflection, which is the ability to assess its memories and re-evaluate
    them. For example, condensting short term memories into long term memories.

    Planning:

    When humans face a complex task, they first break it down into simple subtasks and then
    solve each subtask one by one. The planning module empowers LLM-based agents with the ability
    to think and plan for solving complex tasks, which makes the agent more comprehensive,
    powerful, and reliable. The two key methods to consider are: Planning with feedback and planning
    without feedback.

    Action:

    Actions translate the agents decisions into specific outcomes. For example, if the agent
    decides to write a file, the action would be to write the file. There are many approaches you
    could implement actions.

    The Forge has a basic module for each of these areas. However, you are free to implement your own.
    This is just a starting point.
    """

    def __init__(self, database: AgentDB, workspace: Workspace):
        """
        The database is used to store tasks, steps and artifact metadata. The workspace is used to
        store artifacts. The workspace is a directory on the file system.

        Feel free to create subclasses of the database and workspace to implement your own storage
        """
        super().__init__(database, workspace)

    async def execute_step(self, task_id: str, step_request: StepRequestBody) -> Step:
        import requests
        import json
        import subprocess

        # 1. Créer l'étape dans la base de données de la Forge
        step = await self.db.create_step(task_id=task_id, input=step_request, is_last=True)
        
        # 2. Récupérer le cahier des charges envoyé par l'utilisateur
        cahier_des_charges = step_request.input
        print(f"\n🧠 [VIEILagent] Nouveau cahier des charges reçu : {cahier_des_charges}")

        # 3. Configurer l'appel à ton Ollama local (ex: sur ton Orange Pi ou PC)
        OLLAMA_URL = "http://localhost:11434/api/generate"  # Mets l'IP de ton Orange Pi si Ollama est dessus
        MODEL_NAME = "qwen2.5-coder:7b" # Ou deepseek-coder, llama3, etc.

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
            response = requests.post(OLLAMA_URL, json=payload, timeout=60)
            result = response.json()
            code_genere = result.get("response", "").strip()
            
            # Nettoyage rapide des balises markdown ```cpp si le modèle en a mis
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

        # 6. SANDBOX : Phase de test de compilation automatique en tâche de fond !
        # On récupère le chemin absolu du fichier dans le workspace pour le compiler
        chemin_complet_cpp = self.workspace.get_path(task_id=task_id, path=nom_fichier)
        chemin_binaire = chemin_complet_cpp.replace(".cpp", "")

        print("⚙️ Lancement de la compilation de test (g++)...")
        compilation = subprocess.run(
            ["g++", "-O3", str(chemin_complet_cpp), "-o", str(chemin_binaire)],
            capture_output=True, text=True
        )

        if compilation.returncode == 0:
            status_output = f"✅ Application compilée avec succès ! Le binaire est prêt.\n\nCode généré :\n{code_genere}"
            print("🚀 Compilation réussie !")
        else:
            status_output = f"❌ Erreur de compilation détectée par la Sandbox :\n{compilation.stderr}"
            print("⚠️ Le code généré comporte une erreur de syntaxe.")

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
