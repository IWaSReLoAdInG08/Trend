"""
Advanced Data Analysis Tools

Provides heat trend analysis, platform comparison, keyword co-occurrence, sentiment analysis, etc.
English-only implementation for ASCII safety.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from difflib import SequenceMatcher

from ..services.data_service import DataService
from ..utils.validators import (
    validate_platforms,
    validate_limit,
    validate_keyword,
    validate_top_n,
    validate_date_range
)
from ..utils.errors import MCPError, InvalidParameterError, DataNotFoundError


def calculate_news_weight(news_data: Dict, rank_threshold: int = 5) -> float:
    """
    Calculate news weight (for sorting)

    - Rank Weight (60%): Position in the list
    - Frequency Weight (30%): Number of occurrences
    - Hotness Weight (10%): Proportion of high rankings
    """
    ranks = news_data.get("ranks", [])
    if not ranks:
        return 0.0

    count = news_data.get("count", len(ranks))

    # Weight configuration (consistent with config.yaml)
    RANK_WEIGHT = 0.6
    FREQUENCY_WEIGHT = 0.3
    HOTNESS_WEIGHT = 0.1

    # 1. Rank weight
    rank_scores = []
    for rank in ranks:
        score = 11 - min(rank, 10)
        rank_scores.append(score)

    rank_weight = sum(rank_scores) / len(ranks) if ranks else 0

    # 2. Frequency weight: min(count, 10) * 10
    frequency_weight = min(count, 10) * 10

    # 3. Hotness bonus: high_rank_ratio * 100
    high_rank_count = sum(1 for rank in ranks if rank <= rank_threshold)
    hotness_ratio = high_rank_count / len(ranks) if ranks else 0
    hotness_weight = hotness_ratio * 100

    return (
        rank_weight * RANK_WEIGHT
        + frequency_weight * FREQUENCY_WEIGHT
        + hotness_weight * HOTNESS_WEIGHT
    )


class AnalyticsTools:
    """Advanced Data Analysis Tools Class"""

    def __init__(self, project_root: str = None):
        """Initialize analysis tools"""
        self.data_service = DataService(project_root)

    def analyze_data_insights_unified(
        self,
        insight_type: str = "platform_compare",
        topic: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
        min_frequency: int = 3,
        top_n: int = 20
    ) -> Dict:
        """Unified Data Insights Analysis Tool"""
        try:
            if insight_type not in ["platform_compare", "platform_activity", "keyword_cooccur"]:
                raise InvalidParameterError(
                    f"Invalid insight type: {insight_type}",
                    suggestion="Supported: platform_compare, platform_activity, keyword_cooccur"
                )

            if insight_type == "platform_compare":
                return self.compare_platforms(topic=topic, date_range=date_range)
            elif insight_type == "platform_activity":
                return self.get_platform_activity_stats(date_range=date_range)
            else:
                return self.analyze_keyword_cooccurrence(min_frequency=min_frequency, top_n=top_n)

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def analyze_topic_trend_unified(
        self,
        topic: str,
        analysis_type: str = "trend",
        date_range: Optional[Dict[str, str]] = None,
        granularity: str = "day",
        threshold: float = 3.0,
        time_window: int = 24,
        lookahead_hours: int = 6,
        confidence_threshold: float = 0.7
    ) -> Dict:
        """Unified Topic Trend Analysis Tool"""
        try:
            topic = validate_keyword(topic)
            if analysis_type not in ["trend", "lifecycle", "viral", "predict"]:
                raise InvalidParameterError(f"Invalid analysis type: {analysis_type}")

            if analysis_type == "trend":
                return self.get_topic_trend_analysis(topic=topic, date_range=date_range, granularity=granularity)
            elif analysis_type == "lifecycle":
                return self.analyze_topic_lifecycle(topic=topic, date_range=date_range)
            elif analysis_type == "viral":
                return self.detect_viral_topics(threshold=threshold, time_window=time_window)
            else:
                return self.predict_trending_topics(lookahead_hours=lookahead_hours, confidence_threshold=confidence_threshold)

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def get_topic_trend_analysis(
        self,
        topic: str,
        date_range: Optional[Dict[str, str]] = None,
        granularity: str = "day"
    ) -> Dict:
        """Track heat changes of a specific topic"""
        try:
            topic = validate_keyword(topic)
            if granularity != "day":
                raise InvalidParameterError("Only 'day' granularity is currently supported")

            if date_range:
                start_date, end_date = validate_date_range(date_range)
            else:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=6)

            trend_data = []
            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(date=current_date)
                    count = 0
                    matched = []
                    for _, titles in all_titles.items():
                        for title in titles.keys():
                            if topic.lower() in title.lower():
                                count += 1
                                matched.append(title)
                    trend_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": count,
                        "sample_titles": matched[:3]
                    })
                except DataNotFoundError:
                    trend_data.append({"date": current_date.strftime("%Y-%m-%d"), "count": 0, "sample_titles": []})
                current_date += timedelta(days=1)

            counts = [item["count"] for item in trend_data]
            total_days = (end_date - start_date).days + 1
            max_count = max(counts) if counts else 0
            change_rate = 0
            if len(counts) >= 2:
                first = next((c for c in counts if c > 0), 0)
                if first > 0:
                    change_rate = ((counts[-1] - first) / first) * 100

            return {
                "success": True,
                "topic": topic,
                "date_range": {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d")},
                "trend_data": trend_data,
                "statistics": {
                    "total_mentions": sum(counts),
                    "peak_count": max_count,
                    "change_rate": round(change_rate, 2)
                },
                "trend_direction": "Rising" if change_rate > 10 else "Falling" if change_rate < -10 else "Stable"
            }
        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def compare_platforms(
        self,
        topic: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict:
        """Compare platform attention to a topic"""
        try:
            if topic: topic = validate_keyword(topic)
            start_date, end_date = validate_date_range(date_range) if date_range else (datetime.now(), datetime.now())

            platform_stats = defaultdict(lambda: {"total_news": 0, "topic_mentions": 0, "unique_titles": set(), "top_keywords": Counter()})
            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(date=current_date)
                    for pid, titles in all_titles.items():
                        pname = id_to_name.get(pid, pid)
                        for title in titles.keys():
                            platform_stats[pname]["total_news"] += 1
                            platform_stats[pname]["unique_titles"].add(title)
                            if topic and topic.lower() in title.lower():
                                platform_stats[pname]["topic_mentions"] += 1
                            platform_stats[pname]["top_keywords"].update(self._extract_keywords(title))
                except DataNotFoundError:
                    pass
                current_date += timedelta(days=1)

            result_stats = {}
            for platform, stats in platform_stats.items():
                coverage = (stats["topic_mentions"] / stats["total_news"]) * 100 if stats["total_news"] > 0 else 0
                result_stats[platform] = {
                    "total_news": stats["total_news"],
                    "topic_mentions": stats["topic_mentions"],
                    "coverage_rate": round(coverage, 2),
                    "top_keywords": [{"keyword": k, "count": v} for k, v in stats["top_keywords"].most_common(5)]
                }

            return {
                "success": True,
                "topic": topic,
                "platform_stats": result_stats,
                "total_platforms": len(result_stats)
            }
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}

    def analyze_keyword_cooccurrence(self, min_frequency: int = 3, top_n: int = 20) -> Dict:
        """Analyze which keywords frequently appear together"""
        try:
            min_frequency = validate_limit(min_frequency, default=3)
            top_n = validate_top_n(top_n)
            all_titles, _, _ = self.data_service.parser.read_all_titles_for_date()

            cooccurrence = Counter()
            kw_titles = defaultdict(list)
            for _, titles in all_titles.items():
                for title in titles.keys():
                    keywords = self._extract_keywords(title)
                    for kw in keywords: kw_titles[kw].append(title)
                    if len(keywords) >= 2:
                        for i, k1 in enumerate(keywords):
                            for k2 in keywords[i+1:]:
                                pair = tuple(sorted([k1, k2]))
                                cooccurrence[pair] += 1

            top_pairs = [p for p in cooccurrence.most_common(top_n) if p[1] >= min_frequency]
            result_pairs = []
            for (k1, k2), count in top_pairs:
                both = [t for t in kw_titles[k1] if k2 in self._extract_keywords(t)]
                result_pairs.append({"keyword1": k1, "keyword2": k2, "count": count, "samples": both[:3]})

            return {"success": True, "pairs": result_pairs, "total": len(result_pairs)}
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}

    def analyze_sentiment(
        self,
        topic: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        date_range: Optional[Dict[str, str]] = None,
        limit: int = 50,
        sort_by_weight: bool = True,
        include_url: bool = False
    ) -> Dict:
        """Collect news for AI sentiment analysis"""
        try:
            if topic: topic = validate_keyword(topic)
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)
            start_date, end_date = validate_date_range(date_range) if date_range else (datetime.now(), datetime.now())

            all_items = []
            curr = start_date
            while curr <= end_date:
                try:
                    titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(date=curr, platform_ids=platforms)
                    for pid, platform_titles in titles.items():
                        name = id_to_name.get(pid, pid)
                        for title, info in platform_titles.items():
                            if topic and topic.lower() not in title.lower(): continue
                            item = {"platform": name, "title": title, "ranks": info.get("ranks", []), "date": curr.strftime("%Y-%m-%d")}
                            if include_url:
                                item["url"] = info.get("url", "")
                                item["mobileUrl"] = info.get("mobileUrl", "")
                            all_items.append(item)
                except DataNotFoundError: pass
                curr += timedelta(days=1)

            if not all_items: return {"success": False, "message": "No related news found"}

            unique = {}
            for item in all_items:
                key = f"{item['platform']}::{item['title']}"
                if key not in unique: unique[key] = item
                else: unique[key]["ranks"].extend(item["ranks"])
            
            deduped = list(unique.values())
            if sort_by_weight:
                deduped.sort(key=lambda x: calculate_news_weight(x), reverse=True)
            
            selected = deduped[:limit]
            return {
                "success": True,
                "summary": {"total": len(deduped), "count": len(selected), "topic": topic},
                "ai_prompt": self._create_sentiment_analysis_prompt(selected, topic),
                "news_sample": selected
            }
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}

    def _create_sentiment_analysis_prompt(self, news_data: List[Dict], topic: Optional[str]) -> str:
        """Create AI prompt for sentiment analysis"""
        prompt = [f"Please analyze the sentiment of headlines related to '{topic or 'current news'}'.", ""]
        prompt.append("Requirements: Orientation (Pos/Neg/Neu), stats, platform differences, and overall trend.")
        prompt.append(f"Total items: {len(news_data)}\n")
        
        by_platform = defaultdict(list)
        for item in news_data: by_platform[item["platform"]].append(item["title"])
        
        for platform, titles in by_platform.items():
            prompt.append(f"[{platform}]")
            for i, t in enumerate(titles, 1): prompt.append(f"{i}. {t}")
            prompt.append("")
        
        return "\n".join(prompt)

    def find_similar_news(self, reference_title: str, threshold: float = 0.6, limit: int = 50, include_url: bool = False) -> Dict:
        """Find related news based on title similarity"""
        try:
            ref = validate_keyword(reference_title)
            all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date()
            similar = []
            for pid, platform_titles in all_titles.items():
                name = id_to_name.get(pid, pid)
                for title, info in platform_titles.items():
                    if title == ref: continue
                    sim = self._calculate_similarity(ref, title)
                    if sim >= threshold:
                        item = {"title": title, "platform": name, "similarity": round(sim, 3)}
                        if include_url: item["url"] = info.get("url", "")
                        similar.append(item)
            similar.sort(key=lambda x: x["similarity"], reverse=True)
            return {"success": True, "similar_news": similar[:limit]}
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}

    def search_by_entity(self, entity: str, entity_type: Optional[str] = None, limit: int = 50) -> Dict:
        """Search for news containing specific entities"""
        try:
            entity = validate_keyword(entity)
            all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date()
            results = []
            for pid, platform_titles in all_titles.items():
                name = id_to_name.get(pid, pid)
                for title, info in platform_titles.items():
                    if entity in title:
                        results.append({"title": title, "platform": name, "rank": info.get("ranks", [999])[0]})
            results.sort(key=lambda x: x["rank"])
            return {"success": True, "entity": entity, "results": results[:limit]}
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}

    def generate_summary_report(self, report_type: str = "daily", date_range: Optional[Dict[str, str]] = None) -> Dict:
        """Generate trending summary reports"""
        try:
            start, end = validate_date_range(date_range) if date_range else ((datetime.now(), datetime.now()) if report_type == "daily" else (datetime.now() - timedelta(days=6), datetime.now()))
            
            keywords = Counter()
            platform_counts = Counter()
            all_items = []
            curr = start
            while curr <= end:
                try:
                    titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(date=curr)
                    for pid, platform_titles in titles.items():
                        name = id_to_name.get(pid, pid)
                        platform_counts[name] += len(platform_titles)
                        for title in platform_titles.keys():
                            all_items.append({"title": title, "platform": name})
                            keywords.update(self._extract_keywords(title))
                except DataNotFoundError: pass
                curr += timedelta(days=1)

            report = f"# {report_type.capitalize()} Trending Summary\n\n"
            report += f"**Range**: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}\n\n"
            report += "## Top Keywords\n"
            for kw, count in keywords.most_common(10): report += f"- **{kw}** ({count})\n"
            report += "\n## Platform Activity\n"
            for p, c in platform_counts.most_common(): report += f"- **{p}**: {c} items\n"
            
            return {"success": True, "markdown_report": report}
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}

    def get_platform_activity_stats(self, date_range: Optional[Dict[str, str]] = None) -> Dict:
        """Stats on posting frequency and active periods"""
        try:
            start, end = validate_date_range(date_range) if date_range else (datetime.now(), datetime.now())
            activity = defaultdict(lambda: {"total_news": 0, "active_days": set(), "hourly": Counter()})
            curr = start
            while curr <= end:
                try:
                    titles, id_to_name, timestamps = self.data_service.parser.read_all_titles_for_date(date=curr)
                    for pid, ptitles in titles.items():
                        name = id_to_name.get(pid, pid)
                        activity[name]["total_news"] += len(ptitles)
                        activity[name]["active_days"].add(curr.strftime("%Y-%m-%d"))
                        for fname in timestamps.keys():
                            m = re.match(r'(\d{2})\d{2}\.txt', fname)
                            if m: activity[name]["hourly"][int(m.group(1))] += 1
                except DataNotFoundError: pass
                curr += timedelta(days=1)
            
            res = {}
            for p, s in activity.items():
                top_h = s["hourly"].most_common(3)
                res[p] = {"news": s["total_news"], "days": len(s["active_days"]), "top_hours": [f"{h:02d}:00" for h, _ in top_h]}
            return {"success": True, "platform_activity": res}
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}

    def analyze_topic_lifecycle(self, topic: str, date_range: Optional[Dict[str, str]] = None) -> Dict:
        """Track topic lifecycle from search entries"""
        try:
            topic = validate_keyword(topic)
            start, end = validate_date_range(date_range) if date_range else (datetime.now() - timedelta(days=6), datetime.now())
            history = []
            curr = start
            while curr <= end:
                cnt = 0
                try:
                    titles, _, _ = self.data_service.parser.read_all_titles_for_date(date=curr)
                    for _, ptitles in titles.items():
                        for t in ptitles.keys():
                            if topic.lower() in t.lower(): cnt += 1
                except DataNotFoundError: pass
                history.append({"date": curr.strftime("%Y-%m-%d"), "count": cnt})
                curr += timedelta(days=1)
            
            counts = [h["count"] for h in history]
            if not any(counts): return {"success": False, "message": "Topic not found"}
            
            peak = max(counts)
            avg = sum(counts) / len(counts)
            stage = "Rising" if counts[-1] > avg else "Declining"
            return {"success": True, "topic": topic, "history": history, "analysis": {"peak": peak, "average": round(avg, 2), "stage": stage}}
        except Exception as e:
            return {"success": False, "error": {"message": str(e)}}

    def detect_viral_topics(self, threshold: float = 3.0, time_window: int = 24) -> Dict:
        """Identify topics with sudden burst in heat"""
        try:
            curr_titles, _, _ = self.data_service.parser.read_all_titles_for_date()
            prev_titles = {}
            try: prev_titles, _, _ = self.data_service.parser.read_all_titles_for_date(date=datetime.now() - timedelta(days=1))
            except: pass
            
            curr_kw = Counter()
            kw_samples = defaultdict(list)
            for _, ts in curr_titles.items():
                for t in ts.keys():
                    kws = self._extract_keywords(t)
                    curr_kw.update(kws)
                    for k in kws: kw_samples[k].append(t)
            
            prev_kw = Counter()
            for _, ts in prev_titles.items():
                for t in ts.keys(): prev_kw.update(self._extract_keywords(t))
                
            viral = []
            for kw, c in curr_kw.items():
                p = prev_kw.get(kw, 0)
                if p == 0:
                    if c >= 5: viral.append({"keyword": kw, "count": c, "growth": "New", "samples": kw_samples[kw][:3]})
                elif c / p >= threshold:
                    viral.append({"keyword": kw, "count": c, "growth": round(c/p, 2), "samples": kw_samples[kw][:3]})
            return {"success": True, "viral_topics": sorted(viral, key=lambda x: (x["growth"] if x["growth"] != "New" else 999), reverse=True)}
        except Exception as e: return {"success": False, "error": {"message": str(e)}}

    def predict_trending_topics(self, lookahead_hours: int = 6, confidence_threshold: float = 0.7) -> Dict:
        """Predict potential hotspots based on trend growth"""
        try:
            trends = defaultdict(list)
            for d in range(3, -1, -1):
                try:
                    ts, _, _ = self.data_service.parser.read_all_titles_for_date(date=datetime.now() - timedelta(days=d))
                    kc = Counter()
                    for _, pt in ts.items():
                        for t in pt.keys(): kc.update(self._extract_keywords(t))
                    for k, c in kc.items(): trends[k].append(c)
                except: pass
            
            preds = []
            for kw, data in trends.items():
                if len(data) < 2: continue
                growth = (data[-1] - data[-2]) / data[-2] if data[-2] > 0 else (1.0 if data[-1] >= 3 else 0)
                if growth > 0.3:
                    preds.append({"keyword": kw, "growth": round(growth*100, 2), "prediction": "Potential Hotspot"})
            return {"success": True, "predictions": sorted(preds, key=lambda x: x["growth"], reverse=True)[:20]}
        except Exception as e: return {"success": False, "error": {"message": str(e)}}

    def _extract_keywords(self, title: str, min_length: int = 2) -> List[str]:
        """Simple keyword extraction"""
        title = re.sub(r'http[s]?://\S+', '', title)
        title = re.sub(r'[^\w\s]', ' ', title)
        words = re.split(r'[\s,.:;!?-]+', title)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'to', 'in', 'on', 'at', 'by', 'is', 'are', 'was', 'were'}
        return [w.strip() for w in words if w.strip() and len(w.strip()) >= min_length and w.strip().lower() not in stopwords]

    def _calculate_similarity(self, t1: str, t2: str) -> float:
        """Calculate line similarity"""
        return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()

    def _find_unique_topics(self, platform_stats: Dict) -> Dict[str, List[str]]:
        """Find keywords unique to specific platforms"""
        res = {}
        all_kw = {}
        for p, s in platform_stats.items():
            all_kw[p] = set([k for k, _ in s["top_keywords"].most_common(10)])
        for p, kws in all_kw.items():
            others = set().union(*[v for k, v in all_kw.items() if k != p])
            unique = kws - others
            if unique: res[p] = list(unique)[:5]
        return res
