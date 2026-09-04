import re
import json
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime


class Severity(Enum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"

    def __str__(self):
        return self.value


class SeverityEncoder(json.JSONEncoder):
    """Кастомный JSON-encoder для обработки Enum Severity."""
    def default(self, obj):
        if isinstance(obj, Severity):
            return obj.value
        return super().default(obj)

@dataclass
class Issue:
    severity: Severity
    message: str
    suggestion: str

@dataclass
class SentenceAnalysis:
    sentence_id: int
    text: str
    issues: List[Dict[str, str]]
    timestamp: str
    extracted_entities: Dict[str, List[str]]
    process_mentions: List[str]
    agentive_violations: List[str]

class AccumulativeOntoLinter:
    """
    Онтологический линтер с накопительной памятью.
    Анализирует предложения и накапливает информацию в JSON-структуре.
    """
    
    # Слова и суффиксы, указывающие на процесс
    PROCESS_SUFFIXES = (
        'ание', 'ение', 'ятие', 'тие', 'ование', 'ирование',
        'ство', 'ция', 'ость'
    )
    # Дополнительные процессные слова
    PROCESS_WORDS_EXTRA = {
        'интуиция', 'логика', 'эмпатия', 'совесть', 'воля',
        'сознание', 'понимание', 'внимание', 'ощущение',
        'восприятие', 'мышление', 'переживание', 'чувствование'
    }
    # Исключения - слова с процессными суффиксами, но НЕ процессы
    PROCESS_SUFFIX_EXCEPTIONS = {
        'здание', 'создание', 'издание', 'название', 'призвание',
        'послание', 'писание', 'одеяние', 'влияние', 'стояние',
        'местоимение', 'предложение', 'упражнение', 'усилие',
        'оружие', 'племя', 'время', 'бремя', 'знамя', 'семя',
        'пламя', 'вымя', 'темя', 'стремя', 'корысть', 'масть',
        'часть', 'власть', 'честь', 'пасть', 'кость', 'роспись',
        'живопись', 'летопись', 'пропись', 'картопись', 'степь',
        'дверь', 'церковь', 'мать', 'дочь', 'ночь', 'мышь',
        'ложь', 'рожь', 'плоть', 'нить', 'грусть', 'радость',
        'молодость', 'старость', 'новость', 'готовность',
        'способность', 'возможность', 'необходимость', 'действительность'
    }

    # Посессивные конструкции
    POSSESSIVE_PATTERNS = [
        r"\bмо[йяё]\s+(\w+)",
        r"\bтво[йяё]\s+(\w+)",
        r"\bего\s+(\w+)",
        r"\bеё\s+(\w+)",
        r"\bее\s+(\w+)",
        r"\bих\s+(\w+)",
        r"\bу\s+меня\s+есть\s+(\w+)",
        r"\bу\s+тебя\s+есть\s+(\w+)",
        r"\bу\s+него\s+есть\s+(\w+)",
        r"\bу\s+неё\s+есть\s+(\w+)",
        r"\bу\s+нее\s+есть\s+(\w+)",
        r"\bу\s+нас\s+есть\s+(\w+)",
        r"\bу\s+них\s+есть\s+(\w+)",
    ]

    # Маркеры конкретного времени/события (инстанс)
    INSTANCE_TIME_MARKERS = [
        'сейчас', 'сегодня', 'вчера', 'завтра', 'утром', 'вечером',
        'только что', 'недавно', 'в тот момент', 'когда', 'пока',
        'во время', 'на встрече', 'на экзамене', 'при переходе',
        'после', 'до', 'в течение', 'в данный момент', 'на этой неделе'
    ]

    # Глаголы динамики
    DYNAMIC_VERBS = [
        'растёт', 'рассеялось', 'отвлеклось', 'привлекло', 'пришло',
        'ушло', 'изменилось', 'улучшилось', 'ухудшилось', 'появилось',
        'исчезло', 'возникло', 'пропало', 'вернулось', 'сместилось',
        'сконцентрировалось', 'расфокусировалось', 'обострилось',
        'меняется', 'протекает', 'развивается', 'ослабевает', 'усиливается'
    ]

    # Агентивные глаголы (процесс не может их выполнять)
    AGENTIVE_VERBS = [
        'подвела', 'подвёл', 'подвело', 'не подвела', 'не подвёл', 'не подвело',
        'помогла', 'помог', 'помогло', 'не помогла', 'не помог', 'не помогло',
        'спасла', 'спас', 'спасло', 'не спасла', 'не спас', 'не спасло',
        'решила', 'решил', 'решило', 'захотела', 'захотел', 'захотело',
        'сделала', 'сделал', 'сделало', 'выполнила', 'выполнил', 'выполнило',
        'сработала', 'сработал', 'сработало', 'не сработала', 'не сработал',
        'обманула', 'обманул', 'обмануло', 'удивила', 'удивил', 'удивило',
        'подсказала', 'подсказал', 'подсказало'
    ]

    # Связки гипостазирования
    COPULA_PATTERNS = [
        r"\b(\w+)\s+(?:есть|является|суть)\s+(.+)"
    ]

    # Бинарные предикаты о процессах
    BINARY_PROCESS_PATTERNS = [
        (r"\b(сознател[её]н|обладает сознанием|имеет сознание|не обладает сознанием|не имеет сознания)\b", "сознание"),
        (r"\b(понимает|не понимает|осознаёт|не осознаёт)\b", "понимание/осознание"),
        (r"\b(чувствует|не чувствует)\b", "чувствование"),
    ]

    # Абсолютные слова
    ABSOLUTE_WORDS = ['всегда', 'никогда', 'везде', 'нигде', 'абсолютно', 'в принципе']

    def __init__(self):
        # Накопительное хранилище
        self.knowledge_base: Dict[str, Any] = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_sentences": 0,
                "total_issues": 0,
                "error_count": 0,
                "warn_count": 0
            },
            "sentences": [],
            "accumulated_entities": {
                "processes_mentioned": [],
                "agentive_violations": [],
                "possessive_constructions": [],
                "absolute_statements": []
            },
            "summary": {
                "recurring_issues": {},
                "entity_frequency": {}
            }
        }
        self._sentence_counter = 0

    def is_process_word(self, word: str) -> bool:
        w = word.lower()
        if w in self.PROCESS_SUFFIX_EXCEPTIONS:
            return False
        if w.endswith(self.PROCESS_SUFFIXES):
            return True
        if w in self.PROCESS_WORDS_EXTRA:
            return True
        return False

    def has_instance_markers(self, text: str) -> bool:
        for marker in self.INSTANCE_TIME_MARKERS:
            if marker in text.lower():
                return True
        for verb in self.DYNAMIC_VERBS:
            if verb in text.lower():
                return True
        return False

    def has_agentive_verb(self, text: str) -> bool:
        for verb in self.AGENTIVE_VERBS:
            if verb in text.lower():
                return True
        return False

    def is_first_person_present(self, text: str) -> bool:
        text_lower = text.lower()
        if 'я ' in text_lower or text_lower.startswith('я '):
            if not re.search(r"\b(был|была|было|буду|будешь|будет|будем|будете|будут)\b", text_lower):
                return True
        return False

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Извлекает сущности из текста для накопления."""
        entities = {
            "processes": [],
            "possessives": [],
            "absolutes": [],
            "agents": []
        }
        
        # Извлекаем процессные слова
        words = re.findall(r'\b\w+\b', text)
        for word in words:
            if self.is_process_word(word) and word.lower() not in entities["processes"]:
                entities["processes"].append(word.lower())
        
        # Извлекаем посессивные конструкции
        for pattern in self.POSSESSIVE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                captured = match.group(1).lower()
                if self.is_process_word(captured) and captured not in entities["possessives"]:
                    entities["possessives"].append(captured)
        
        # Извлекаем абсолютные слова
        for word in self.ABSOLUTE_WORDS:
            if word in text.lower() and word not in entities["absolutes"]:
                entities["absolutes"].append(word)
        
        # Извлекаем агентивные нарушения
        if self.has_agentive_verb(text):
            for verb in self.AGENTIVE_VERBS:
                if verb in text.lower():
                    entities["agents"].append(verb)
        
        return entities

    def check_possession_of_type(self, text: str) -> List[Issue]:
        issues = []
        for pattern in self.POSSESSIVE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                captured_word = match.group(1)
                if self.is_process_word(captured_word):
                    if self.has_agentive_verb(text):
                        issues.append(Issue(
                            severity=Severity.ERROR,
                            message=f"Попытка действия процесса. Процесс '{captured_word}' не может быть субъектом.",
                            suggestion="Процесс не выполняет действия. Укажите реального субъекта или опишите состояние."
                        ))
                        continue
                    if self.has_instance_markers(text) or self.is_first_person_present(text):
                        continue
                    issues.append(Issue(
                        severity=Severity.ERROR,
                        message=f"Попытка обладать типом процесса: '{match.group(0)}'",
                        suggestion=(
                            f"Укажите конкретное проявление (время, динамику) или переформулируйте "
                            f"без собственничества, например: 'происходит {captured_word.lower()}'"
                        )
                    ))
        return issues

    def check_copula_hypostasis(self, text: str) -> List[Issue]:
        issues = []
        for pattern in self.COPULA_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                subject = match.group(1).lower()
                if self.is_process_word(subject):
                    issues.append(Issue(
                        severity=Severity.WARN,
                        message=f"Связка 'быть' с процессом '{subject}': возможно гипостазирование.",
                        suggestion=f"Опишите в терминах активности: '{subject} проявляется как ...'"
                    ))
        return issues

    def check_binary_process_judgments(self, text: str) -> List[Issue]:
        issues = []
        for pattern, process_name in self.BINARY_PROCESS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(Issue(
                    severity=Severity.ERROR,
                    message=f"Бинарное суждение о континуальном процессе '{process_name}'.",
                    suggestion=f"Укажите степень/интенсивность, напр. 'степень {process_name} = 0.7'"
                ))
        return issues

    def check_absolutes(self, text: str) -> List[Issue]:
        issues = []
        if any(word in text.lower() for word in self.ABSOLUTE_WORDS):
            if self.is_first_person_present(text) or re.search(r"\bя\s+(был|была|было|никогда|всегда|помню|знаю|думаю)\b", text, re.IGNORECASE):
                return issues
            if not re.search(r"\d|наблюд|эксперимент|данные|пример", text, re.IGNORECASE):
                issues.append(Issue(
                    severity=Severity.WARN,
                    message="Абсолютное утверждение без эмпирической привязки.",
                    suggestion="Добавьте условия проверяемости или ограничьте временные рамки."
                ))
        return issues

    def analyze_sentence(self, text: str) -> SentenceAnalysis:
        """Анализирует одно предложение и возвращает структурированный результат."""
        self._sentence_counter += 1
        
        issues = []
        issues.extend(self.check_possession_of_type(text))
        issues.extend(self.check_copula_hypostasis(text))
        issues.extend(self.check_binary_process_judgments(text))
        issues.extend(self.check_absolutes(text))
        
        entities = self.extract_entities(text)
        process_mentions = entities["processes"]
        agentive_violations = entities["agents"]
        
        analysis = SentenceAnalysis(
            sentence_id=self._sentence_counter,
            text=text,
            issues=[asdict(i) for i in issues],
            timestamp=datetime.now().isoformat(),
            extracted_entities=entities,
            process_mentions=process_mentions,
            agentive_violations=agentive_violations
        )
        
        return analysis

    def add_sentence(self, text: str) -> Dict[str, Any]:
        """
        Добавляет предложение в накопительную базу знаний.
        Возвращает обновлённое состояние JSON.
        """
        analysis = self.analyze_sentence(text)
        analysis_dict = asdict(analysis)
        
        # Добавляем предложение в список
        self.knowledge_base["sentences"].append(analysis_dict)
        
        # Обновляем счётчики
        self.knowledge_base["metadata"]["total_sentences"] += 1
        self.knowledge_base["metadata"]["total_issues"] += len(analysis.issues)
        
        for issue in analysis.issues:
            if issue["severity"] == "ERROR":
                self.knowledge_base["metadata"]["error_count"] += 1
            elif issue["severity"] == "WARN":
                self.knowledge_base["metadata"]["warn_count"] += 1
        
        # Накопление сущностей
        for proc in analysis.process_mentions:
            if proc not in self.knowledge_base["accumulated_entities"]["processes_mentioned"]:
                self.knowledge_base["accumulated_entities"]["processes_mentioned"].append(proc)
        
        for violation in analysis.agentive_violations:
            if violation not in self.knowledge_base["accumulated_entities"]["agentive_violations"]:
                self.knowledge_base["accumulated_entities"]["agentive_violations"].append(violation)
        
        for poss in analysis.extracted_entities["possessives"]:
            if poss not in self.knowledge_base["accumulated_entities"]["possessive_constructions"]:
                self.knowledge_base["accumulated_entities"]["possessive_constructions"].append(poss)
        
        for absolute in analysis.extracted_entities["absolutes"]:
            if absolute not in self.knowledge_base["accumulated_entities"]["absolute_statements"]:
                self.knowledge_base["accumulated_entities"]["absolute_statements"].append(absolute)
        
        # Обновляем сводку по повторяющимся проблемам
        for issue in analysis.issues:
            key = issue["message"]
            if key not in self.knowledge_base["summary"]["recurring_issues"]:
                self.knowledge_base["summary"]["recurring_issues"][key] = 0
            self.knowledge_base["summary"]["recurring_issues"][key] += 1
        
        # Обновляем частоту сущностей
        for proc in analysis.process_mentions:
            if proc not in self.knowledge_base["summary"]["entity_frequency"]:
                self.knowledge_base["summary"]["entity_frequency"][proc] = 0
            self.knowledge_base["summary"]["entity_frequency"][proc] += 1
        
        return self.get_json()

    def get_json(self) -> Dict[str, Any]:
        """Возвращает текущее состояние базы знаний как JSON-совместимый dict."""
        return self.knowledge_base

    def export_json(self, indent: int = 2) -> str:
        """Экспортирует базу знаний в JSON-строку."""
        return json.dumps(self.knowledge_base, cls=SeverityEncoder, ensure_ascii=False, indent=indent)

    def reset(self):
        """Сбрасывает накопительную базу знаний."""
        self.__init__()


def main():
    linter = AccumulativeOntoLinter()
    print("Онтологический линтер v3 (накопительный)")
    print("Вводите предложения на русском языке.")
    print("Команды:")
    print("  'json' - показать накопленный JSON")
    print("  'reset' - сбросить базу знаний")
    print("  'exit' или 'выход' - завершить работу\n")
    
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ('exit', 'выход', 'quit'):
            print("\nФинальный JSON:")
            print(linter.export_json())
            break
        
        if user_input.lower() == 'json':
            print("\n=== Текущее состояние JSON ===")
            print(linter.export_json())
            print("=== Конец JSON ===\n")
            continue
        
        if user_input.lower() == 'reset':
            linter.reset()
            print("База знаний сброшена.\n")
            continue
        
        # Анализируем предложение
        result = linter.add_sentence(user_input)
        
        # Показываем краткий результат
        last_sentence = result["sentences"][-1]
        print(f"\nПредложение #{last_sentence['sentence_id']}:")
        
        if last_sentence['issues']:
            print(f"  Найдено проблем: {len(last_sentence['issues'])}")
            for issue in last_sentence['issues']:
                print(f"  [{issue['severity']}] {issue['message']}")
                print(f"    → {issue['suggestion']}")
        else:
            print("  OK (нет выявленных проблем)")
        
        if last_sentence['process_mentions']:
            print(f"  Процессы: {', '.join(last_sentence['process_mentions'])}")
        
        print(f"\n  Всего предложений в базе: {result['metadata']['total_sentences']}")
        print(f"  Всего проблем: {result['metadata']['total_issues']}")
        print()


if __name__ == "__main__":
    main()
